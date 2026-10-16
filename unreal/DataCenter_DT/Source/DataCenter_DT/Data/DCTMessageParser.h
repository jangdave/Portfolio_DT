// 게이트웨이가 보내는 JSON(매니페스트, WebSocket 메시지)을 읽는다. 네트워크와 분리해서 자동화 테스트로 검증한다.
#pragma once

#include "CoreMinimal.h"
#include "Core/DCTTypes.h"

enum class EDCTMessageType : uint8
{
	Unknown,
	Snapshot,
	Sample,
	Alarm,
	Scenario,
	Aggregate,
};

struct FDCTMessage
{
	EDCTMessageType Type = EDCTMessageType::Unknown;
	TArray<FDCTSensorSample> Samples; // snapshot이면 여러 건, sample이면 한 건
	TArray<FDCTAggregate> Aggregates; // snapshot이면 여러 건, aggregate이면 한 건
	FDCTAlarmEvent Alarm;
	FDCTScenarioEvent Scenario;
	FString ScenarioName; // snapshot에 담긴 현재 시나리오 (없으면 빈 문자열)
};

namespace DCTMessageParser
{
	// GET /api/sensors 응답. 센서가 하나라도 형식이 틀리면 실패로 본다(일부만 쓰면 화면이 조용히 틀어진다).
	DATACENTER_DT_API bool ParseManifest(const FString& Json, TArray<FDCTSensorInfo>& OutSensors, FString& OutError);

	// WebSocket 메시지 한 건. 형식이 틀리면 false.
	DATACENTER_DT_API bool ParseMessage(const FString& Json, FDCTMessage& OutMessage, FString& OutError);
}
