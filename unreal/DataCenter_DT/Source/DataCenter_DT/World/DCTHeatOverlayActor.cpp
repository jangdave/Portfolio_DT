#include "World/DCTHeatOverlayActor.h"

#include "Components/StaticMeshComponent.h"
#include "Core/DCTConfidence.h"
#include "Core/DCTTempGradient.h"
#include "Data/DCTConnectionSubsystem.h"
#include "Engine/GameInstance.h"
#include "Engine/StaticMesh.h"
#include "EngineUtils.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "UObject/ConstructorHelpers.h"
#include "USDStageActor.h"

ADCTHeatOverlayActor::ADCTHeatOverlayActor()
{
	PrimaryActorTick.bCanEverTick = false;
	SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));

	static ConstructorHelpers::FObjectFinder<UStaticMesh> CubeFinder(TEXT("/Engine/BasicShapes/Cube.Cube"));
	static ConstructorHelpers::FObjectFinder<UMaterialInterface> MaterialFinder(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
	CubeMesh = CubeFinder.Object;
	BaseMaterial = MaterialFinder.Object;
}

void ADCTHeatOverlayActor::BeginPlay()
{
	Super::BeginPlay();

	for (TActorIterator<AUsdStageActor> It(GetWorld()); It; ++It)
	{
		StageActor = *It;
		break;
	}
	if (!StageActor.IsValid())
	{
		UE_LOG(LogDCT, Warning, TEXT("온도 표시: 레벨에 USD Stage Actor가 없어 판을 세우지 않는다"));
		return;
	}
	if (UGameInstance* GameInstance = GetGameInstance())
	{
		Connection = GameInstance->GetSubsystem<UDCTConnectionSubsystem>();
	}
	if (UDCTConnectionSubsystem* Subsystem = Connection.Get())
	{
		SampleHandle = Subsystem->Hub().OnSample.AddUObject(this, &ADCTHeatOverlayActor::HandleSample);
		SnapshotHandle = Subsystem->Hub().OnSnapshot.AddUObject(this, &ADCTHeatOverlayActor::HandleSnapshot);
	}
}

void ADCTHeatOverlayActor::EndPlay(const EEndPlayReason::Type Reason)
{
	if (UDCTConnectionSubsystem* Subsystem = Connection.Get())
	{
		Subsystem->Hub().OnSample.Remove(SampleHandle);
		Subsystem->Hub().OnSnapshot.Remove(SnapshotHandle);
	}
	Super::EndPlay(Reason);
}

void ADCTHeatOverlayActor::HandleSnapshot()
{
	// 다시 접속해 새 snapshot이 오면 판을 처음부터 다시 맞춘다(센서 목록이 바뀌었을 수 있다)
	Missing.Reset();
	NumMissingLogged = 0;
}

void ADCTHeatOverlayActor::EnsurePlate(const FString& SensorId)
{
	if (Materials.Contains(SensorId) || Missing.Contains(SensorId))
	{
		return;
	}
	UDCTConnectionSubsystem* Subsystem = Connection.Get();
	AUsdStageActor* Stage = StageActor.Get();
	const FDCTSensorInfo* Info = Subsystem ? Subsystem->Hub().Registry().Find(SensorId) : nullptr;
	if (!Info || !Stage || Info->Metric != Metric)
	{
		return;
	}

	USceneComponent* Anchor = Stage->GetGeneratedComponent(Info->UsdPath);
	if (!Anchor)
	{
		Missing.Add(SensorId);
		if (++NumMissingLogged <= 5)
		{
			UE_LOG(LogDCT, Warning, TEXT("온도 표시: 장면에서 앵커를 찾지 못했다: %s"), *Info->UsdPath);
		}
		return;
	}

	UStaticMeshComponent* Plate = NewObject<UStaticMeshComponent>(this, *FString::Printf(TEXT("Plate_%s"), *SensorId));
	Plate->SetStaticMesh(CubeMesh);
	Plate->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Plate->SetCastShadow(false);
	Plate->SetupAttachment(GetRootComponent());
	Plate->RegisterComponent();

	// 앵커의 월드 위치와 방향에 놓는다(부모로 붙이지 않는다: USD를 다시 불러와 앵커가 사라져도 판이 같이 사라지지 않게)
	FTransform Transform = Anchor->GetComponentTransform();
	Transform.AddToTranslation(Transform.GetRotation().RotateVector(FVector(0.0, 0.0, PlateCenterOffsetZCm)));
	Transform.SetScale3D(PlateSizeCm / 100.0); // 기본 큐브는 한 변 100 cm
	Plate->SetWorldTransform(Transform);

	UMaterialInstanceDynamic* Material = UMaterialInstanceDynamic::Create(BaseMaterial, this);
	Plate->SetMaterial(0, Material);
	Materials.Add(SensorId, Material);

	// 신뢰 막대: 판 윗면 위. 처음에는 숨기고, 구간과 등급이 오면 보인다.
	UStaticMeshComponent* Bar = NewObject<UStaticMeshComponent>(this, *FString::Printf(TEXT("Bar_%s"), *SensorId));
	Bar->SetStaticMesh(CubeMesh);
	Bar->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Bar->SetCastShadow(false);
	Bar->SetupAttachment(GetRootComponent());
	Bar->RegisterComponent();
	Bar->SetVisibility(false);
	FTransform BarTransform = Anchor->GetComponentTransform();
	BarTransform.AddToTranslation(BarTransform.GetRotation().RotateVector(FVector(0.0, 0.0, PlateCenterOffsetZCm + PlateSizeCm.Z * 0.5 + ConfidenceBarHeightCm * 0.5 + 1.0)));
	BarBase.Add(SensorId, BarTransform);
	UMaterialInstanceDynamic* BarMaterial = UMaterialInstanceDynamic::Create(BaseMaterial, this);
	Bar->SetMaterial(0, BarMaterial);
	Bars.Add(SensorId, Bar);
	BarMaterials.Add(SensorId, BarMaterial);
	if (Materials.Num() % 20 == 0)
	{
		UE_LOG(LogDCT, Log, TEXT("온도 표시: 판 %d개를 세웠다"), Materials.Num());
	}
}

void ADCTHeatOverlayActor::HandleSample(const FDCTSensorSample& Sample)
{
	EnsurePlate(Sample.SensorId);
	if (TObjectPtr<UMaterialInstanceDynamic>* Material = Materials.Find(Sample.SensorId))
	{
		(*Material)->SetVectorParameterValue(TEXT("Color"), DCTTempGradient::ForSample(Sample, ColdValue, HotValue));
	}
	if (TObjectPtr<UStaticMeshComponent>* Bar = Bars.Find(Sample.SensorId))
	{
		const double Fraction = bShowConfidenceBar ? DCTConfidence::BarFraction(Sample, ConfidenceFullWidth) : 0.0;
		(*Bar)->SetVisibility(Fraction > 0.0);
		if (Fraction > 0.0)
		{
			FTransform Transform = BarBase.FindRef(Sample.SensorId);
			Transform.SetScale3D(FVector(PlateSizeCm.X * Fraction, PlateSizeCm.Y, ConfidenceBarHeightCm) / 100.0);
			(*Bar)->SetWorldTransform(Transform);
			BarMaterials.FindRef(Sample.SensorId)->SetVectorParameterValue(TEXT("Color"), DCTConfidence::ColorFor(Sample.Confidence));
		}
	}
}
