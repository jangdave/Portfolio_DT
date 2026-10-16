#include "World/DCTWorldSubsystem.h"

#include "Core/DCTTypes.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
#include "USDStageActor.h"
#include "World/DCTHeatOverlayActor.h"

namespace
{
	TAutoConsoleVariable<int32> CVarOverlay(TEXT("dct.Overlay"), 1, TEXT("1이면 Play가 시작될 때 USD 장면 위에 온도 표시를 자동으로 세운다."));
}

bool UDCTWorldSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* World = Cast<UWorld>(Outer);
	return World && (World->IsGameWorld()) && Super::ShouldCreateSubsystem(Outer);
}

void UDCTWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	if (CVarOverlay.GetValueOnGameThread() == 0)
	{
		return;
	}
	TActorIterator<AUsdStageActor> StageIt(&InWorld);
	if (!StageIt)
	{
		return; // USD 장면이 없는 레벨에서는 아무것도 하지 않는다
	}
	TActorIterator<ADCTHeatOverlayActor> OverlayIt(&InWorld);
	if (OverlayIt)
	{
		return; // 레벨에 이미 놓여 있으면 그것을 쓴다
	}
	FActorSpawnParameters Params;
	Params.ObjectFlags |= RF_Transient; // 레벨에 저장되지 않는다
	InWorld.SpawnActor<ADCTHeatOverlayActor>(FVector::ZeroVector, FRotator::ZeroRotator, Params);
	UE_LOG(LogDCT, Log, TEXT("온도 표시 액터를 자동으로 세웠다"));
}
