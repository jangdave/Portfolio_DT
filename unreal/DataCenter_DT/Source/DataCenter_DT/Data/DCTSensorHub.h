// 센서 목록, 최근 값, 알람 모델을 한데 묶고 게이트웨이 메시지를 반영한다. 네트워크를 모르기 때문에 자동화 테스트로 검증한다.
#pragma once

#include "CoreMinimal.h"
#include "Data/DCTMessageParser.h"
#include "Data/DCTSensorModel.h"

class DATACENTER_DT_API FDCTSensorHub
{
public:
	DECLARE_MULTICAST_DELEGATE_OneParam(FOnSample, const FDCTSensorSample&);
	DECLARE_MULTICAST_DELEGATE_OneParam(FOnAggregate, const FDCTAggregate&);
	DECLARE_MULTICAST_DELEGATE_OneParam(FOnScenario, const FDCTScenarioEvent&);
	DECLARE_MULTICAST_DELEGATE(FOnSnapshot);

	FOnSample OnSample;       // 값이 반영될 때마다(snapshot의 센서도 한 건씩)
	FOnAggregate OnAggregate; // 집계 값이 바뀔 때
	FOnScenario OnScenario;
	FOnSnapshot OnSnapshot;   // snapshot을 모두 반영한 뒤 한 번
	// 알람 변화는 AlarmModel().OnAlarmChanged

	FDCTSensorRegistry& Registry() { return SensorRegistry; }
	const FDCTSensorRegistry& Registry() const { return SensorRegistry; }
	FDCTSampleStore& Store() { return SampleStore; }
	const FDCTSampleStore& Store() const { return SampleStore; }
	FDCTAlarmModel& AlarmModel() { return Alarms; }
	const FDCTAlarmModel& AlarmModel() const { return Alarms; }

	const FDCTAggregate* FindAggregate(const FString& Name) const { return Aggregates.Find(Name); }
	const FString& CurrentScenario() const { return ScenarioName; }
	// 레지스트리에 없는 센서의 값이 와서 버린 횟수
	int32 NumUnknownSensorDrops() const { return UnknownSensorDrops; }

	// 게이트웨이 메시지 하나를 반영한다.
	void ApplyMessage(const FDCTMessage& Message);
	// 연결이 끊겼을 때: 마지막 값은 유지하고 품질만 stale로 바꾼다(docs/12 4장).
	void MarkAllStale();

private:
	void ApplySample(const FDCTSensorSample& Sample);

	FDCTSensorRegistry SensorRegistry;
	FDCTSampleStore SampleStore;
	FDCTAlarmModel Alarms;
	TMap<FString, FDCTAggregate> Aggregates;
	FString ScenarioName;
	int32 UnknownSensorDrops = 0;
};
