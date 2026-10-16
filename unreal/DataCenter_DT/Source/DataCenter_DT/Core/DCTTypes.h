// 센서 데이터 공용 타입. Data, World, UI 계층이 함께 쓴다 (docs/12 3장).
#pragma once

#include "CoreMinimal.h"

DECLARE_LOG_CATEGORY_EXTERN(LogDCT, Log, All);

enum class EDCTAlarmState : uint8
{
	Normal,
	Warn,
	Critical,
};

enum class EDCTQuality : uint8
{
	Good,
	Bad,
	Stale,
};

DATACENTER_DT_API EDCTAlarmState DCTAlarmFromString(const FString& Text);
DATACENTER_DT_API EDCTQuality DCTQualityFromString(const FString& Text);
DATACENTER_DT_API const TCHAR* DCTAlarmToString(EDCTAlarmState State);

// 센서 목록(매니페스트)의 한 줄. docs/11 3장.
struct FDCTSensorInfo
{
	FString SensorId;
	FString Topic;
	FString UsdPath;
	FString EquipmentPath;
	FString EquipmentType;
	FString Metric;
	FString Unit;
	double RangeMin = 0.0;
	double RangeMax = 0.0;
	TOptional<double> Warn;
	TOptional<double> Critical;
	bool bLowIsDanger = false; // direction이 "low"이면 값이 낮을수록 위험하다
};

// 센서 값 한 건. 값이 없으면(snapshot의 빈 자리) Value가 비어 있다.
struct FDCTSensorSample
{
	FString SensorId;
	TOptional<double> Value;
	FString Unit;
	EDCTQuality Quality = EDCTQuality::Stale;
	EDCTAlarmState Alarm = EDCTAlarmState::Normal;
	FDateTime Timestamp = FDateTime(0); // 0이면 시각 없음
};

struct FDCTAlarmEvent
{
	FString SensorId;
	EDCTAlarmState From = EDCTAlarmState::Normal;
	EDCTAlarmState To = EDCTAlarmState::Normal;
	double Value = 0.0;
	FDateTime Timestamp = FDateTime(0);
};

struct FDCTAggregate
{
	FString Name;
	double Value = 0.0;
	FString Unit;
	FDateTime Timestamp = FDateTime(0);
};

struct FDCTScenarioEvent
{
	FString Name;
	bool bStart = true;
	FDateTime Timestamp = FDateTime(0);
};
