// 게임(Play)이 시작될 때 USD Stage Actor가 있는 레벨에 온도 표시 액터를 자동으로 세운다.
// 레벨 파일(.umap)을 고치지 않고도 동작하게 하려는 것이다. 끄려면 콘솔에서 dct.Overlay 0 (Play 전에).
#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "DCTWorldSubsystem.generated.h"

UCLASS()
class DATACENTER_DT_API UDCTWorldSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
};
