#include "Data/DCTSensorHub.h"

void FDCTSensorHub::ApplySample(const FDCTSensorSample& Sample)
{
	if (!SensorRegistry.Find(Sample.SensorId))
	{
		// 센서 목록에 없는 값은 무시하고 로그를 남긴다(docs/12 4장). 같은 로그가 쏟아지지 않게 처음 몇 번만 쓴다.
		if (++UnknownSensorDrops <= 5)
		{
			UE_LOG(LogDCT, Warning, TEXT("센서 목록에 없는 센서의 값을 버렸다: %s"), *Sample.SensorId);
		}
		return;
	}
	SampleStore.Apply(Sample);
	OnSample.Broadcast(Sample);
}

void FDCTSensorHub::ApplyMessage(const FDCTMessage& Message)
{
	switch (Message.Type)
	{
	case EDCTMessageType::Snapshot:
		// 접속 직후의 전체 상태: 이전 값과 알람을 지우고 그대로 덮어쓴다(변화 알림은 보내지 않는다).
		SampleStore.Clear();
		Alarms.Clear();
		Aggregates.Reset();
		ScenarioName = Message.ScenarioName;
		for (const FDCTSensorSample& Sample : Message.Samples)
		{
			ApplySample(Sample);
			if (SensorRegistry.Find(Sample.SensorId))
			{
				Alarms.SetState(Sample.SensorId, Sample.Alarm);
			}
		}
		for (const FDCTAggregate& Agg : Message.Aggregates)
		{
			Aggregates.Add(Agg.Name, Agg);
			OnAggregate.Broadcast(Agg);
		}
		OnSnapshot.Broadcast();
		break;

	case EDCTMessageType::Sample:
		for (const FDCTSensorSample& Sample : Message.Samples)
		{
			ApplySample(Sample);
		}
		break;

	case EDCTMessageType::Alarm:
		if (SensorRegistry.Find(Message.Alarm.SensorId))
		{
			Alarms.Apply(Message.Alarm);
		}
		break;

	case EDCTMessageType::Scenario:
		ScenarioName = Message.Scenario.bStart ? Message.Scenario.Name : FString();
		OnScenario.Broadcast(Message.Scenario);
		break;

	case EDCTMessageType::Aggregate:
		for (const FDCTAggregate& Agg : Message.Aggregates)
		{
			Aggregates.Add(Agg.Name, Agg);
			OnAggregate.Broadcast(Agg);
		}
		break;

	default:
		break;
	}
}

void FDCTSensorHub::MarkAllStale()
{
	SampleStore.MarkAllStale();
}
