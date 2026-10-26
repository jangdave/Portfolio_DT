// 랙 입구 온도를 3D 장면 위에 색으로 보여 준다 (docs/12 5장).
// 센서 목록의 usdPath로 USD Stage의 센서 앵커 컴포넌트를 찾고, 그 자리에 얇은 판을 세워 값에 따라 색을 바꾼다.
// 장비 메시의 재질은 건드리지 않는다(USD 재질을 바꾸지 않아서 USD를 다시 불러와도 안전하다).
#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "DCTHeatOverlayActor.generated.h"

class AUsdStageActor;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UStaticMesh;
class UStaticMeshComponent;
class UDCTConnectionSubsystem;
struct FDCTSensorSample;

UCLASS()
class DATACENTER_DT_API ADCTHeatOverlayActor : public AActor
{
	GENERATED_BODY()

public:
	ADCTHeatOverlayActor();

	// 이 지표(metric)의 센서에 판을 세운다
	UPROPERTY(EditAnywhere, Category = "DCT")
	FString Metric = TEXT("temp_in");

	// 색 범위(섭씨). 이 아래는 파랑, 위는 빨강
	UPROPERTY(EditAnywhere, Category = "DCT")
	double ColdValue = 18.0;

	UPROPERTY(EditAnywhere, Category = "DCT")
	double HotValue = 35.0;

	// 판 크기(cm): 폭, 두께, 높이. 앵커의 로컬 축 기준(랙 앞면이 로컬 Y 방향)
	UPROPERTY(EditAnywhere, Category = "DCT")
	FVector PlateSizeCm = FVector(50.0, 2.0, 180.0);

	// 앵커(랙 높이 120 cm, 앞면에서 5 cm 앞)에서 판 중심까지의 높이 차이(cm). 랙 높이 약 200 cm의 가운데쯤에 오도록 아래로 옮긴다.
	UPROPERTY(EditAnywhere, Category = "DCT")
	double PlateCenterOffsetZCm = -30.0;

	// 신뢰 막대(보정 모델이 구간과 등급을 보낸 센서에만 보인다): 판 위의 얇은 막대. 색은 등급, 길이는 90% 구간 폭(좁을수록 길다).
	UPROPERTY(EditAnywhere, Category = "DCT")
	bool bShowConfidenceBar = true;

	// 구간 폭이 이 값(섭씨) 이상이면 막대가 가장 짧아진다
	UPROPERTY(EditAnywhere, Category = "DCT")
	double ConfidenceFullWidth = 4.0;

	// 막대 두께(높이, cm)
	UPROPERTY(EditAnywhere, Category = "DCT")
	double ConfidenceBarHeightCm = 8.0;

	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;

private:
	void HandleSample(const FDCTSensorSample& Sample);
	void HandleSnapshot();
	void EnsurePlate(const FString& SensorId);

	TWeakObjectPtr<AUsdStageActor> StageActor;
	TWeakObjectPtr<UDCTConnectionSubsystem> Connection;
	FDelegateHandle SampleHandle;
	FDelegateHandle SnapshotHandle;

	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<UMaterialInstanceDynamic>> Materials;

	// 센서별 신뢰 막대(구성요소, 재질, 막대 기준 위치)
	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<UStaticMeshComponent>> Bars;

	UPROPERTY(Transient)
	TMap<FString, TObjectPtr<UMaterialInstanceDynamic>> BarMaterials;

	TMap<FString, FTransform> BarBase;

	UPROPERTY(Transient)
	TObjectPtr<UStaticMesh> CubeMesh;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInterface> BaseMaterial;

	TSet<FString> Missing; // 앵커를 못 찾은 센서(같은 경고를 반복하지 않으려고)
	int32 NumMissingLogged = 0;
};
