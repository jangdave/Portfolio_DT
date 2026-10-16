// 센서 목록, 최근 값과 이력, 알람 상태. 화면(UI, World)을 모르는 순수 데이터 계층이다 (docs/12 2, 3장).
// 설계 문서의 UDCTSensorRegistry, UDCTSampleStore, UDCTAlarmModel을 UObject가 필요 없는 일반 클래스로 만들었다.
// 자동화 테스트에서 엔진 객체 없이 바로 만들어 볼 수 있고, 연결 서브시스템이 하나씩 소유한다.
#pragma once

#include "CoreMinimal.h"
#include "Containers/RingBuffer.h"
#include "Core/DCTTypes.h"

// 매니페스트에서 읽은 센서 목록. ID로 센서와 장비를 찾는다.
class DATACENTER_DT_API FDCTSensorRegistry
{
public:
	void Reset(TArray<FDCTSensorInfo> InSensors);
	const FDCTSensorInfo* Find(const FString& SensorId) const;
	// 장비 경로(예: /DC/Hall01/Row01/Rack_01)에 속한 센서 ID
	TArray<FString> SensorsOfEquipment(const FString& EquipmentPath) const;
	const TArray<FDCTSensorInfo>& All() const { return Sensors; }
	int32 Num() const { return Sensors.Num(); }

private:
	TArray<FDCTSensorInfo> Sensors;
	TMap<FString, int32> IndexById;
	TMultiMap<FString, FString> ByEquipment;
};

// 센서별 최근 값과 이력(원형 버퍼). 시각이 뒤로 가는 값은 이력에 넣지 않는다.
class DATACENTER_DT_API FDCTSampleStore
{
public:
	explicit FDCTSampleStore(int32 InHistoryCapacity = 900) : HistoryCapacity(InHistoryCapacity) {}

	// 값을 반영한다. 최근 값은 항상 갱신하고, 이력에는 값이 있고 품질이 stale이 아닌 것만 넣는다.
	void Apply(const FDCTSensorSample& Sample);
	void Clear();
	// 연결이 끊겼을 때: 값은 두고 품질만 stale로 바꾼다(이력에는 넣지 않는다).
	void MarkAllStale();
	const FDCTSensorSample* Latest(const FString& SensorId) const;
	// 오래된 것부터 순서대로
	TArray<FDCTSensorSample> History(const FString& SensorId) const;
	int32 NumSensors() const { return LatestById.Num(); }

private:
	int32 HistoryCapacity;
	TMap<FString, FDCTSensorSample> LatestById;
	TMap<FString, TRingBuffer<FDCTSensorSample>> HistoryById;
};

// 게이트웨이가 알려 준 알람 상태 보관. 목록과 변화 알림을 제공한다.
class DATACENTER_DT_API FDCTAlarmModel
{
public:
	DECLARE_MULTICAST_DELEGATE_OneParam(FOnAlarmChanged, const FDCTAlarmEvent&);
	FOnAlarmChanged OnAlarmChanged;

	// snapshot처럼 센서 상태를 그대로 덮어쓴다(변화 알림은 보내지 않는다).
	void SetState(const FString& SensorId, EDCTAlarmState State);
	// alarm 메시지를 반영한다.
	void Apply(const FDCTAlarmEvent& Event);
	void Clear();
	EDCTAlarmState StateOf(const FString& SensorId) const;
	// 정상이 아닌 센서 ID (위험 먼저)
	TArray<FString> ActiveSensors() const;
	int32 CountOf(EDCTAlarmState State) const;
	// 최근 알람 변화 기록(오래된 것부터, 최대 MaxLog건)
	const TArray<FDCTAlarmEvent>& Log() const { return EventLog; }

private:
	static constexpr int32 MaxLog = 200;
	TMap<FString, EDCTAlarmState> States;
	TArray<FDCTAlarmEvent> EventLog;
};
