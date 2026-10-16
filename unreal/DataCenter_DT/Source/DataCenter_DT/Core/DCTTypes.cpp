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

const TCHAR* DCTAlarmToString(EDCTAlarmState State)
{
	switch (State)
	{
	case EDCTAlarmState::Warn: return TEXT("warn");
	case EDCTAlarmState::Critical: return TEXT("critical");
	default: return TEXT("normal");
	}
}
