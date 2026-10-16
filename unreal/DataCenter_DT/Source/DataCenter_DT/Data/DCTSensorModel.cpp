#include "Data/DCTSensorModel.h"

#include "Algo/Reverse.h"

void FDCTSensorRegistry::Reset(TArray<FDCTSensorInfo> InSensors)
{
	Sensors = MoveTemp(InSensors);
	IndexById.Reset();
	ByEquipment.Reset();
	for (int32 Index = 0; Index < Sensors.Num(); ++Index)
	{
		IndexById.Add(Sensors[Index].SensorId, Index);
		ByEquipment.Add(Sensors[Index].EquipmentPath, Sensors[Index].SensorId);
	}
}

const FDCTSensorInfo* FDCTSensorRegistry::Find(const FString& SensorId) const
{
	const int32* Index = IndexById.Find(SensorId);
	return Index ? &Sensors[*Index] : nullptr;
}

TArray<FString> FDCTSensorRegistry::SensorsOfEquipment(const FString& EquipmentPath) const
{
	TArray<FString> Result;
	ByEquipment.MultiFind(EquipmentPath, Result);
	// MultiFind는 나중에 넣은 것부터 주므로 매니페스트 순서로 되돌린다
	Algo::Reverse(Result);
	return Result;
}

void FDCTSampleStore::Apply(const FDCTSensorSample& Sample)
{
	// 최근 값보다 시각이 앞선(과거) 샘플은 무시한다. 시각이 없는 샘플(snapshot의 빈 자리)은 값이 없을 때만 자리를 채운다.
	if (const FDCTSensorSample* Current = LatestById.Find(Sample.SensorId))
	{
		if (Sample.Timestamp.GetTicks() != 0 && Current->Timestamp.GetTicks() != 0 && Sample.Timestamp < Current->Timestamp)
		{
			return;
		}
		if (Sample.Timestamp.GetTicks() == 0 && Current->Value.IsSet() && !Sample.Value.IsSet())
		{
			return;
		}
	}
	LatestById.Add(Sample.SensorId, Sample);

	if (Sample.Value.IsSet() && Sample.Quality != EDCTQuality::Stale)
	{
		TRingBuffer<FDCTSensorSample>& History = HistoryById.FindOrAdd(Sample.SensorId);
		if (History.Num() >= HistoryCapacity)
		{
			History.PopFront();
		}
		History.Add(Sample);
	}
}

void FDCTSampleStore::Clear()
{
	LatestById.Reset();
	HistoryById.Reset();
}

void FDCTSampleStore::MarkAllStale()
{
	for (TPair<FString, FDCTSensorSample>& Pair : LatestById)
	{
		Pair.Value.Quality = EDCTQuality::Stale;
	}
}

const FDCTSensorSample* FDCTSampleStore::Latest(const FString& SensorId) const
{
	return LatestById.Find(SensorId);
}

TArray<FDCTSensorSample> FDCTSampleStore::History(const FString& SensorId) const
{
	TArray<FDCTSensorSample> Result;
	if (const TRingBuffer<FDCTSensorSample>* History = HistoryById.Find(SensorId))
	{
		Result.Reserve(History->Num());
		for (const FDCTSensorSample& Sample : *History)
		{
			Result.Add(Sample);
		}
	}
	return Result;
}

void FDCTAlarmModel::SetState(const FString& SensorId, EDCTAlarmState State)
{
	if (State == EDCTAlarmState::Normal)
	{
		States.Remove(SensorId);
	}
	else
	{
		States.Add(SensorId, State);
	}
}

void FDCTAlarmModel::Apply(const FDCTAlarmEvent& Event)
{
	SetState(Event.SensorId, Event.To);
	if (EventLog.Num() >= MaxLog)
	{
		EventLog.RemoveAt(0);
	}
	EventLog.Add(Event);
	OnAlarmChanged.Broadcast(Event);
}

void FDCTAlarmModel::Clear()
{
	States.Reset();
	EventLog.Reset();
}

EDCTAlarmState FDCTAlarmModel::StateOf(const FString& SensorId) const
{
	const EDCTAlarmState* State = States.Find(SensorId);
	return State ? *State : EDCTAlarmState::Normal;
}

TArray<FString> FDCTAlarmModel::ActiveSensors() const
{
	TArray<FString> Result;
	States.GenerateKeyArray(Result);
	Result.Sort([this](const FString& A, const FString& B)
	{
		const EDCTAlarmState SA = StateOf(A);
		const EDCTAlarmState SB = StateOf(B);
		return SA != SB ? SA > SB : A < B; // 위험 먼저, 같으면 ID 순
	});
	return Result;
}

int32 FDCTAlarmModel::CountOf(EDCTAlarmState State) const
{
	int32 Count = 0;
	for (const TPair<FString, EDCTAlarmState>& Pair : States)
	{
		Count += (Pair.Value == State) ? 1 : 0;
	}
	return Count;
}
