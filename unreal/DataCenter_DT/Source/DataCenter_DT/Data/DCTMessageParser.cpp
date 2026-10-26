#include "Data/DCTMessageParser.h"

#include "Dom/JsonObject.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

namespace
{
	FDateTime ParseTime(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field)
	{
		FString Text;
		FDateTime Result(0);
		if (Obj->TryGetStringField(Field, Text))
		{
			FDateTime::ParseIso8601(*Text, Result);
		}
		return Result;
	}

	// UE의 TryGetNumber는 "24" 같은 숫자 문자열도 받아 주므로, JSON 숫자(number)만 인정하는 검사를 둔다.
	bool ReadNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, double& Out)
	{
		const TSharedPtr<FJsonValue>* Value = Obj->Values.Find(Field);
		return Value && (*Value)->Type == EJson::Number && (*Value)->TryGetNumber(Out);
	}

	// 값은 숫자이거나 null이다. 다른 형식이면 false.
	bool ReadOptionalNumber(const TSharedPtr<FJsonObject>& Obj, const TCHAR* Field, TOptional<double>& Out)
	{
		const TSharedPtr<FJsonValue>* Value = Obj->Values.Find(Field);
		if (!Value || (*Value)->IsNull())
		{
			Out.Reset();
			return true;
		}
		double Number = 0.0;
		if ((*Value)->Type != EJson::Number || !(*Value)->TryGetNumber(Number))
		{
			return false;
		}
		Out = Number;
		return true;
	}

	bool ReadSample(const TSharedPtr<FJsonObject>& Obj, FDCTSensorSample& Out)
	{
		if (!Obj->TryGetStringField(TEXT("sensorId"), Out.SensorId) || Out.SensorId.IsEmpty())
		{
			return false;
		}
		if (!ReadOptionalNumber(Obj, TEXT("value"), Out.Value))
		{
			return false;
		}
		Obj->TryGetStringField(TEXT("unit"), Out.Unit);
		FString Quality;
		Out.Quality = Obj->TryGetStringField(TEXT("quality"), Quality) ? DCTQualityFromString(Quality) : EDCTQuality::Stale;
		FString Alarm;
		Out.Alarm = Obj->TryGetStringField(TEXT("alarm"), Alarm) ? DCTAlarmFromString(Alarm) : EDCTAlarmState::Normal;
		Out.Timestamp = ParseTime(Obj, TEXT("ts"));
		// 선택 필드: 구간은 숫자 둘이고 lower <= upper일 때만 받는다. 형식이 틀리면 무시하고 값은 그대로 쓴다.
		double Lower = 0.0;
		double Upper = 0.0;
		if (ReadNumber(Obj, TEXT("lower"), Lower) && ReadNumber(Obj, TEXT("upper"), Upper) && Lower <= Upper)
		{
			Out.Lower = Lower;
			Out.Upper = Upper;
		}
		FString Confidence;
		Out.Confidence = Obj->TryGetStringField(TEXT("confidence"), Confidence) ? DCTConfidenceFromString(Confidence) : EDCTConfidence::None;
		return true;
	}

	bool ReadAggregate(const TSharedPtr<FJsonObject>& Obj, FDCTAggregate& Out)
	{
		if (!Obj->TryGetStringField(TEXT("name"), Out.Name) || !ReadNumber(Obj, TEXT("value"), Out.Value))
		{
			return false;
		}
		Obj->TryGetStringField(TEXT("unit"), Out.Unit);
		Out.Timestamp = ParseTime(Obj, TEXT("ts"));
		return true;
	}

	bool ParseObject(const FString& Json, TSharedPtr<FJsonObject>& Out, FString& OutError)
	{
		TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		if (!FJsonSerializer::Deserialize(Reader, Out) || !Out.IsValid())
		{
			OutError = TEXT("JSON 형식이 올바르지 않다");
			return false;
		}
		return true;
	}
}

bool DCTMessageParser::ParseManifest(const FString& Json, TArray<FDCTSensorInfo>& OutSensors, FString& OutError)
{
	OutSensors.Reset();
	TSharedPtr<FJsonObject> Root;
	if (!ParseObject(Json, Root, OutError))
	{
		return false;
	}
	const TArray<TSharedPtr<FJsonValue>>* List = nullptr;
	if (!Root->TryGetArrayField(TEXT("sensors"), List))
	{
		OutError = TEXT("sensors 배열이 없다");
		return false;
	}
	for (int32 Index = 0; Index < List->Num(); ++Index)
	{
		const TSharedPtr<FJsonObject>* ItemPtr = nullptr;
		if (!(*List)[Index]->TryGetObject(ItemPtr))
		{
			OutError = FString::Printf(TEXT("sensors[%d]가 객체가 아니다"), Index);
			return false;
		}
		const TSharedPtr<FJsonObject>& Item = *ItemPtr;
		FDCTSensorInfo Info;
		const TArray<TSharedPtr<FJsonValue>>* Range = nullptr;
		FString Direction;
		const bool bOk = Item->TryGetStringField(TEXT("sensorId"), Info.SensorId) && !Info.SensorId.IsEmpty()
			&& Item->TryGetStringField(TEXT("topic"), Info.Topic)
			&& Item->TryGetStringField(TEXT("usdPath"), Info.UsdPath)
			&& Item->TryGetStringField(TEXT("equipmentPath"), Info.EquipmentPath)
			&& Item->TryGetStringField(TEXT("equipmentType"), Info.EquipmentType)
			&& Item->TryGetStringField(TEXT("metric"), Info.Metric)
			&& Item->TryGetStringField(TEXT("unit"), Info.Unit)
			&& Item->TryGetArrayField(TEXT("range"), Range) && Range->Num() == 2
			&& (*Range)[0]->Type == EJson::Number && (*Range)[1]->Type == EJson::Number
			&& (*Range)[0]->TryGetNumber(Info.RangeMin) && (*Range)[1]->TryGetNumber(Info.RangeMax)
			&& ReadOptionalNumber(Item, TEXT("warn"), Info.Warn)
			&& ReadOptionalNumber(Item, TEXT("critical"), Info.Critical);
		if (!bOk)
		{
			OutError = FString::Printf(TEXT("sensors[%d]의 필드가 빠졌거나 형식이 틀리다"), Index);
			return false;
		}
		Info.bLowIsDanger = Item->TryGetStringField(TEXT("direction"), Direction) && Direction == TEXT("low");
		OutSensors.Add(MoveTemp(Info));
	}
	return true;
}

bool DCTMessageParser::ParseMessage(const FString& Json, FDCTMessage& OutMessage, FString& OutError)
{
	OutMessage = FDCTMessage();
	TSharedPtr<FJsonObject> Root;
	if (!ParseObject(Json, Root, OutError))
	{
		return false;
	}
	FString Type;
	if (!Root->TryGetStringField(TEXT("type"), Type))
	{
		OutError = TEXT("type이 없다");
		return false;
	}

	if (Type == TEXT("sample"))
	{
		FDCTSensorSample Sample;
		if (!ReadSample(Root, Sample))
		{
			OutError = TEXT("sample 형식이 틀리다");
			return false;
		}
		OutMessage.Type = EDCTMessageType::Sample;
		OutMessage.Samples.Add(MoveTemp(Sample));
		return true;
	}
	if (Type == TEXT("snapshot"))
	{
		const TArray<TSharedPtr<FJsonValue>>* Sensors = nullptr;
		if (!Root->TryGetArrayField(TEXT("sensors"), Sensors))
		{
			OutError = TEXT("snapshot에 sensors가 없다");
			return false;
		}
		for (const TSharedPtr<FJsonValue>& Value : *Sensors)
		{
			const TSharedPtr<FJsonObject>* ItemPtr = nullptr;
			FDCTSensorSample Sample;
			if (!Value->TryGetObject(ItemPtr) || !ReadSample(*ItemPtr, Sample))
			{
				OutError = TEXT("snapshot의 센서 한 건이 형식이 틀리다");
				return false;
			}
			OutMessage.Samples.Add(MoveTemp(Sample));
		}
		// aggregates는 { 이름: {name, value, unit, ts} } 객체다
		const TSharedPtr<FJsonObject>* Aggs = nullptr;
		if (Root->TryGetObjectField(TEXT("aggregates"), Aggs))
		{
			for (const TPair<FString, TSharedPtr<FJsonValue>>& Pair : (*Aggs)->Values)
			{
				const TSharedPtr<FJsonObject>* ItemPtr = nullptr;
				FDCTAggregate Agg;
				if (Pair.Value->TryGetObject(ItemPtr) && ReadAggregate(*ItemPtr, Agg))
				{
					OutMessage.Aggregates.Add(MoveTemp(Agg));
				}
			}
		}
		Root->TryGetStringField(TEXT("scenario"), OutMessage.ScenarioName); // null이면 빈 채로 둔다
		OutMessage.Type = EDCTMessageType::Snapshot;
		return true;
	}
	if (Type == TEXT("alarm"))
	{
		FString From, To;
		FDCTAlarmEvent& Alarm = OutMessage.Alarm;
		if (!Root->TryGetStringField(TEXT("sensorId"), Alarm.SensorId) || !Root->TryGetStringField(TEXT("from"), From)
			|| !Root->TryGetStringField(TEXT("to"), To) || !ReadNumber(Root, TEXT("value"), Alarm.Value))
		{
			OutError = TEXT("alarm 형식이 틀리다");
			return false;
		}
		Alarm.From = DCTAlarmFromString(From);
		Alarm.To = DCTAlarmFromString(To);
		Alarm.Timestamp = ParseTime(Root, TEXT("ts"));
		OutMessage.Type = EDCTMessageType::Alarm;
		return true;
	}
	if (Type == TEXT("scenario"))
	{
		FString Event;
		if (!Root->TryGetStringField(TEXT("name"), OutMessage.Scenario.Name) || !Root->TryGetStringField(TEXT("event"), Event))
		{
			OutError = TEXT("scenario 형식이 틀리다");
			return false;
		}
		OutMessage.Scenario.bStart = (Event == TEXT("start"));
		OutMessage.Scenario.Timestamp = ParseTime(Root, TEXT("ts"));
		OutMessage.Type = EDCTMessageType::Scenario;
		return true;
	}
	if (Type == TEXT("aggregate"))
	{
		FDCTAggregate Agg;
		if (!ReadAggregate(Root, Agg))
		{
			OutError = TEXT("aggregate 형식이 틀리다");
			return false;
		}
		OutMessage.Type = EDCTMessageType::Aggregate;
		OutMessage.Aggregates.Add(MoveTemp(Agg));
		return true;
	}
	OutError = FString::Printf(TEXT("모르는 type: %s"), *Type);
	return false;
}
