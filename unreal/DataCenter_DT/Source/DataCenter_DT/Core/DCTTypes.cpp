#include "Core/DCTTypes.h"

DEFINE_LOG_CATEGORY(LogDCT);

EDCTAlarmState DCTAlarmFromString(const FString& Text)
{
	if (Text == TEXT("critical")) return EDCTAlarmState::Critical;
	if (Text == TEXT("warn")) return EDCTAlarmState::Warn;
	return EDCTAlarmState::Normal;
}

EDCTQuality DCTQualityFromString(const FString& Text)
{
	if (Text == TEXT("good")) return EDCTQuality::Good;
	if (Text == TEXT("bad")) return EDCTQuality::Bad;
	return EDCTQuality::Stale;
}

EDCTConfidence DCTConfidenceFromString(const FString& Text)
{
	if (Text == TEXT("ok")) return EDCTConfidence::Ok;
	if (Text == TEXT("caution")) return EDCTConfidence::Caution;
	if (Text == TEXT("low")) return EDCTConfidence::Low;
	if (Text == TEXT("fallback")) return EDCTConfidence::Fallback;
	return EDCTConfidence::None; // 모르는 값은 등급 없음으로 본다
}

const TCHAR* DCTConfidenceToString(EDCTConfidence Confidence)
{
	switch (Confidence)
	{
	case EDCTConfidence::Ok: return TEXT("ok");
	case EDCTConfidence::Caution: return TEXT("caution");
	case EDCTConfidence::Low: return TEXT("low");
	case EDCTConfidence::Fallback: return TEXT("fallback");
	default: return TEXT("none");
	}
}

const TCHAR* DCTAlarmToString(EDCTAlarmState State)
{
	switch (State)
	{
	case EDCTAlarmState::Warn: return TEXT("warn");
	case EDCTAlarmState::Critical: return TEXT("critical");
	default: return TEXT("normal");
	}
}
