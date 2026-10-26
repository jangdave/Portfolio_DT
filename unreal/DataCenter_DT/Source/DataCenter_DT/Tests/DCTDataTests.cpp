// 데이터 계층 자동화 테스트 (docs/12 8장). 실행: 에디터 Session Frontend > Automation에서 "DCT.Data"
// 또는 명령줄: UnrealEditor-Cmd DataCenter_DT.uproject -ExecCmds="Automation RunTests DCT.Data; Quit" -unattended -nullrhi
#include "Misc/AutomationTest.h"

#if WITH_DEV_AUTOMATION_TESTS

#include "Core/DCTConfidence.h"
#include "Core/DCTTempGradient.h"
#include "Data/DCTMessageParser.h"
#include "Data/DCTSensorHub.h"

namespace
{
	const TCHAR* ManifestJson = TEXT(R"({"version":1,"hall":"hall01","sensors":[
		{"sensorId":"H01-RK01-TEMP-IN","topic":"dct/v1/hall01/rack_01/temp_in","usdPath":"/DC/Hall01/Row01/Rack_01/Anchors/Sensor_TEMP_IN","equipmentPath":"/DC/Hall01/Row01/Rack_01","equipmentType":"rack","metric":"temp_in","unit":"degC","range":[10,45],"warn":27,"critical":32},
		{"sensorId":"H01-RK01-POWER","topic":"dct/v1/hall01/rack_01/power","usdPath":"/DC/Hall01/Row01/Rack_01/Anchors/Sensor_POWER","equipmentPath":"/DC/Hall01/Row01/Rack_01","equipmentType":"rack","metric":"power","unit":"kW","range":[0,15],"warn":null,"critical":null},
		{"sensorId":"H01-CR01-FAN-SPEED","topic":"dct/v1/hall01/crac_01/fan_speed","usdPath":"/DC/Hall01/Cooling/CRAC_01/Anchors/Sensor_FAN_SPEED","equipmentPath":"/DC/Hall01/Cooling/CRAC_01","equipmentType":"crac","metric":"fan_speed","unit":"percent","range":[0,100],"warn":20,"critical":5,"direction":"low"}
	]})");

	void LoadHub(FDCTSensorHub& Hub)
	{
		TArray<FDCTSensorInfo> Sensors;
		FString Error;
		DCTMessageParser::ParseManifest(ManifestJson, Sensors, Error);
		Hub.Registry().Reset(MoveTemp(Sensors));
	}

	bool Apply(FDCTSensorHub& Hub, const FString& Json)
	{
		FDCTMessage Message;
		FString Error;
		if (!DCTMessageParser::ParseMessage(Json, Message, Error))
		{
			return false;
		}
		Hub.ApplyMessage(Message);
		return true;
	}

	FString SampleJson(const TCHAR* Id, double Value, int32 Second, const TCHAR* Quality = TEXT("good"))
	{
		return FString::Printf(TEXT(R"({"type":"sample","sensorId":"%s","value":%g,"unit":"degC","quality":"%s","ts":"2026-10-15T09:00:%02d.000Z"})"), Id, Value, Quality, Second);
	}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDCTManifestTest, "DCT.Data.Manifest", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDCTManifestTest::RunTest(const FString& Parameters)
{
	TArray<FDCTSensorInfo> Sensors;
	FString Error;
	TestTrue(TEXT("정상 목록은 읽힌다"), DCTMessageParser::ParseManifest(ManifestJson, Sensors, Error));
	TestEqual(TEXT("센서 개수"), Sensors.Num(), 3);
	TestEqual(TEXT("주의 기준"), Sensors[0].Warn.Get(-1.0), 27.0);
	TestFalse(TEXT("null 기준은 비어 있다"), Sensors[1].Warn.IsSet());
	TestTrue(TEXT("낮을수록 위험"), Sensors[2].bLowIsDanger);

	FDCTSensorRegistry Registry;
	Registry.Reset(MoveTemp(Sensors));
	TestNotNull(TEXT("ID로 찾기"), Registry.Find(TEXT("H01-RK01-POWER")));
	TestNull(TEXT("없는 ID"), Registry.Find(TEXT("없음")));
	const TArray<FString> OfRack = Registry.SensorsOfEquipment(TEXT("/DC/Hall01/Row01/Rack_01"));
	TestEqual(TEXT("장비의 센서"), OfRack.Num(), 2);
	TestEqual(TEXT("매니페스트 순서"), OfRack[0], FString(TEXT("H01-RK01-TEMP-IN")));

	// 일부만 틀려도 목록 전체를 받지 않는다
	TArray<FDCTSensorInfo> Bad;
	TestFalse(TEXT("필드가 빠진 센서"), DCTMessageParser::ParseManifest(TEXT(R"({"sensors":[{"sensorId":"A"}]})"), Bad, Error));
	TestFalse(TEXT("깨진 JSON"), DCTMessageParser::ParseManifest(TEXT("{깨짐"), Bad, Error));
	TestFalse(TEXT("sensors 없음"), DCTMessageParser::ParseManifest(TEXT("{}"), Bad, Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDCTMessageTest, "DCT.Data.Message", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDCTMessageTest::RunTest(const FString& Parameters)
{
	FDCTMessage Message;
	FString Error;
	TestTrue(TEXT("sample"), DCTMessageParser::ParseMessage(SampleJson(TEXT("H01-RK01-TEMP-IN"), 24.6, 1), Message, Error));
	TestEqual(TEXT("종류"), Message.Type, EDCTMessageType::Sample);
	TestEqual(TEXT("값"), Message.Samples[0].Value.Get(0.0), 24.6);
	TestEqual(TEXT("품질"), Message.Samples[0].Quality, EDCTQuality::Good);
	TestEqual(TEXT("시각(초)"), Message.Samples[0].Timestamp.GetSecond(), 1);

	TestTrue(TEXT("alarm"), DCTMessageParser::ParseMessage(TEXT(R"({"type":"alarm","sensorId":"X","from":"normal","to":"critical","value":33,"ts":"2026-10-15T09:00:05.000Z"})"), Message, Error));
	TestEqual(TEXT("알람 새 상태"), Message.Alarm.To, EDCTAlarmState::Critical);

	TestTrue(TEXT("scenario"), DCTMessageParser::ParseMessage(TEXT(R"({"type":"scenario","name":"cooling_failure","event":"start","ts":"2026-10-15T09:00:00.000Z"})"), Message, Error));
	TestTrue(TEXT("시작"), Message.Scenario.bStart);

	TestTrue(TEXT("snapshot"), DCTMessageParser::ParseMessage(
		TEXT(R"({"type":"snapshot","ts":null,"scenario":null,"sensors":[{"sensorId":"H01-RK01-POWER","value":null,"unit":"kW","quality":"stale","ts":null,"alarm":"normal"},{"sensorId":"H01-RK01-TEMP-IN","value":28.1,"unit":"degC","quality":"good","ts":"2026-10-15T09:00:00.000Z","alarm":"warn"}],"aggregates":{"pue":{"name":"pue","value":1.13,"unit":"ratio","ts":"2026-10-15T09:00:00.000Z"}}})"), Message, Error));
	TestEqual(TEXT("snapshot 센서 수"), Message.Samples.Num(), 2);
	TestFalse(TEXT("값 null은 비어 있다"), Message.Samples[0].Value.IsSet());
	TestEqual(TEXT("알람 상태"), Message.Samples[1].Alarm, EDCTAlarmState::Warn);
	TestEqual(TEXT("집계 수"), Message.Aggregates.Num(), 1);
	TestTrue(TEXT("시나리오 null은 빈 문자열"), Message.ScenarioName.IsEmpty());

	TestFalse(TEXT("깨진 JSON"), DCTMessageParser::ParseMessage(TEXT("{"), Message, Error));
	TestFalse(TEXT("type 없음"), DCTMessageParser::ParseMessage(TEXT("{}"), Message, Error));
	TestFalse(TEXT("모르는 type"), DCTMessageParser::ParseMessage(TEXT(R"({"type":"x"})"), Message, Error));
	TestFalse(TEXT("값이 문자열"), DCTMessageParser::ParseMessage(TEXT(R"({"type":"sample","sensorId":"A","value":"24"})"), Message, Error));
	TestFalse(TEXT("sensorId 없음"), DCTMessageParser::ParseMessage(TEXT(R"({"type":"sample","value":1})"), Message, Error));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDCTStoreTest, "DCT.Data.SampleStore", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDCTStoreTest::RunTest(const FString& Parameters)
{
	FDCTSampleStore Store(3); // 이력 3건
	auto Make = [](double Value, int32 Second, EDCTQuality Quality = EDCTQuality::Good)
	{
		FDCTSensorSample Sample;
		Sample.SensorId = TEXT("A");
		Sample.Value = Value;
		Sample.Quality = Quality;
		Sample.Timestamp = FDateTime(2026, 10, 15, 9, 0, Second);
		return Sample;
	};
	for (int32 Second = 1; Second <= 5; ++Second)
	{
		Store.Apply(Make(Second * 10.0, Second));
	}
	TestEqual(TEXT("최근 값"), Store.Latest(TEXT("A"))->Value.Get(0.0), 50.0);
	const TArray<FDCTSensorSample> History = Store.History(TEXT("A"));
	TestEqual(TEXT("이력은 용량만큼만"), History.Num(), 3);
	TestEqual(TEXT("가장 오래된 것부터"), History[0].Value.Get(0.0), 30.0);

	Store.Apply(Make(1.0, 2)); // 과거 시각은 무시
	TestEqual(TEXT("과거 샘플은 최근 값을 바꾸지 않는다"), Store.Latest(TEXT("A"))->Value.Get(0.0), 50.0);

	Store.Apply(Make(60.0, 6, EDCTQuality::Stale));
	TestEqual(TEXT("stale은 이력에 안 넣는다"), Store.History(TEXT("A")).Num(), 3);
	TestEqual(TEXT("stale도 최근 값에는 반영"), Store.Latest(TEXT("A"))->Quality, EDCTQuality::Stale);

	Store.Apply(Make(70.0, 7));
	Store.MarkAllStale();
	TestEqual(TEXT("끊기면 값은 두고 stale"), Store.Latest(TEXT("A"))->Value.Get(0.0), 70.0);
	TestEqual(TEXT("끊기면 stale"), Store.Latest(TEXT("A"))->Quality, EDCTQuality::Stale);
	TestEqual(TEXT("없는 센서의 이력은 빈 배열"), Store.History(TEXT("없음")).Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDCTHubTest, "DCT.Data.Hub", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDCTHubTest::RunTest(const FString& Parameters)
{
	FDCTSensorHub Hub;
	LoadHub(Hub);

	int32 AlarmEvents = 0;
	Hub.AlarmModel().OnAlarmChanged.AddLambda([&AlarmEvents](const FDCTAlarmEvent&) { ++AlarmEvents; });

	// snapshot: 값이 있는 센서와 빈 자리, 알람 상태, 시나리오
	Apply(Hub, TEXT(R"({"type":"snapshot","scenario":"cooling_failure","sensors":[{"sensorId":"H01-RK01-TEMP-IN","value":33,"unit":"degC","quality":"good","ts":"2026-10-15T09:00:00.000Z","alarm":"critical"},{"sensorId":"H01-RK01-POWER","value":null,"unit":"kW","quality":"stale","ts":null,"alarm":"normal"},{"sensorId":"모르는센서","value":1,"unit":"x","quality":"good","ts":"2026-10-15T09:00:00.000Z","alarm":"warn"}],"aggregates":{}})"));
	TestEqual(TEXT("목록에 있는 센서만 반영(snapshot)"), Hub.Store().NumSensors(), 2);
	TestEqual(TEXT("목록에 없는 센서는 버린다"), Hub.NumUnknownSensorDrops(), 1);
	TestEqual(TEXT("snapshot 알람 상태"), Hub.AlarmModel().StateOf(TEXT("H01-RK01-TEMP-IN")), EDCTAlarmState::Critical);
	TestEqual(TEXT("목록에 없는 센서의 알람은 넣지 않는다"), Hub.AlarmModel().ActiveSensors().Num(), 1);
	TestEqual(TEXT("snapshot은 알람 변화 알림을 보내지 않는다"), AlarmEvents, 0);
	TestEqual(TEXT("시나리오 이름"), Hub.CurrentScenario(), FString(TEXT("cooling_failure")));

	// 실시간 알람 변화
	Apply(Hub, TEXT(R"({"type":"alarm","sensorId":"H01-RK01-TEMP-IN","from":"critical","to":"warn","value":30,"ts":"2026-10-15T09:00:10.000Z"})"));
	TestEqual(TEXT("알람 변화"), Hub.AlarmModel().StateOf(TEXT("H01-RK01-TEMP-IN")), EDCTAlarmState::Warn);
	TestEqual(TEXT("알람 변화 알림 1회"), AlarmEvents, 1);
	TestEqual(TEXT("알람 기록"), Hub.AlarmModel().Log().Num(), 1);
	Apply(Hub, TEXT(R"({"type":"alarm","sensorId":"모르는센서","from":"normal","to":"warn","value":1,"ts":"2026-10-15T09:00:11.000Z"})"));
	TestEqual(TEXT("목록에 없는 센서의 알람은 무시"), AlarmEvents, 1);

	// 위험 먼저 정렬
	Apply(Hub, TEXT(R"({"type":"alarm","sensorId":"H01-CR01-FAN-SPEED","from":"normal","to":"critical","value":3,"ts":"2026-10-15T09:00:12.000Z"})"));
	const TArray<FString> Active = Hub.AlarmModel().ActiveSensors();
	TestEqual(TEXT("정상이 아닌 센서 수"), Active.Num(), 2);
	TestEqual(TEXT("위험이 먼저"), Active[0], FString(TEXT("H01-CR01-FAN-SPEED")));

	// 시나리오 끝, 집계
	Apply(Hub, TEXT(R"({"type":"aggregate","name":"pue","value":1.21,"unit":"ratio","ts":"2026-10-15T09:00:13.000Z"})"));
	TestNotNull(TEXT("집계"), Hub.FindAggregate(TEXT("pue")));
	Apply(Hub, TEXT(R"({"type":"scenario","name":"cooling_failure","event":"end","ts":"2026-10-15T09:01:00.000Z"})"));
	TestTrue(TEXT("시나리오가 끝나면 이름이 비워진다"), Hub.CurrentScenario().IsEmpty());

	// 연결 끊김
	Apply(Hub, SampleJson(TEXT("H01-RK01-TEMP-IN"), 25.0, 20));
	Hub.MarkAllStale();
	TestEqual(TEXT("끊기면 stale"), Hub.Store().Latest(TEXT("H01-RK01-TEMP-IN"))->Quality, EDCTQuality::Stale);
	TestEqual(TEXT("끊겨도 값은 유지"), Hub.Store().Latest(TEXT("H01-RK01-TEMP-IN"))->Value.Get(0.0), 25.0);

	// 새 snapshot은 이전 알람을 지운다(다시 접속했을 때)
	Apply(Hub, TEXT(R"({"type":"snapshot","scenario":null,"sensors":[],"aggregates":{}})"));
	TestEqual(TEXT("새 snapshot이 알람을 지운다"), Hub.AlarmModel().ActiveSensors().Num(), 0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDCTTempGradientTest, "DCT.Data.TempGradient", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDCTTempGradientTest::RunTest(const FString& Parameters)
{
	const FLinearColor Cold = DCTTempGradient::FromValue(18.0, 18.0, 35.0);
	const FLinearColor Hot = DCTTempGradient::FromValue(35.0, 18.0, 35.0);
	TestTrue(TEXT("낮은 값은 파랑"), Cold.B > Cold.R && Cold.B > Cold.G);
	TestTrue(TEXT("높은 값은 빨강"), Hot.R > Hot.G && Hot.R > Hot.B);
	TestTrue(TEXT("범위 밖은 양 끝 색으로 자른다"), DCTTempGradient::FromValue(-50.0, 18.0, 35.0).Equals(Cold) && DCTTempGradient::FromValue(99.0, 18.0, 35.0).Equals(Hot));
	const FLinearColor Mid = DCTTempGradient::FromValue(26.5, 18.0, 35.0);
	TestTrue(TEXT("가운데는 초록과 노랑 사이"), Mid.G > Mid.B && Mid.G > 0.5f);

	FDCTSensorSample Sample;
	Sample.SensorId = TEXT("A");
	TestTrue(TEXT("값이 없으면 회색"), DCTTempGradient::ForSample(Sample, 18.0, 35.0).Equals(FLinearColor(0.25f, 0.25f, 0.25f)));
	Sample.Value = 30.0;
	Sample.Quality = EDCTQuality::Bad;
	TestTrue(TEXT("범위 밖 값은 자홍"), DCTTempGradient::ForSample(Sample, 18.0, 35.0).Equals(FLinearColor(0.8f, 0.0f, 0.8f)));
	Sample.Quality = EDCTQuality::Stale;
	TestTrue(TEXT("오래된 값은 회색"), DCTTempGradient::ForSample(Sample, 18.0, 35.0).Equals(FLinearColor(0.35f, 0.35f, 0.35f)));
	Sample.Quality = EDCTQuality::Good;
	TestTrue(TEXT("정상 값은 값 색"), DCTTempGradient::ForSample(Sample, 18.0, 35.0).Equals(DCTTempGradient::FromValue(30.0, 18.0, 35.0)));
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FDCTConfidenceTest, "DCT.Data.Confidence", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FDCTConfidenceTest::RunTest(const FString& Parameters)
{
	// 구간과 등급은 선택 필드다: 있으면 읽고, 없거나 형식이 틀리면 값은 그대로 두고 등급만 비운다.
	FDCTMessage Message;
	FString Error;
	TestTrue(TEXT("구간과 등급이 있는 sample"), DCTMessageParser::ParseMessage(TEXT(R"({"type":"sample","sensorId":"A","value":24.6,"unit":"degC","quality":"good","ts":"2026-10-15T09:00:01.000Z","lower":24.0,"upper":25.4,"confidence":"caution"})"), Message, Error));
	TestEqual(TEXT("하한"), Message.Samples[0].Lower.Get(0.0), 24.0);
	TestEqual(TEXT("상한"), Message.Samples[0].Upper.Get(0.0), 25.4);
	TestEqual(TEXT("등급"), Message.Samples[0].Confidence, EDCTConfidence::Caution);

	TestTrue(TEXT("필드가 없는 sample"), DCTMessageParser::ParseMessage(SampleJson(TEXT("A"), 24.6, 1), Message, Error));
	TestFalse(TEXT("구간 없음"), Message.Samples[0].Lower.IsSet() || Message.Samples[0].Upper.IsSet());
	TestEqual(TEXT("등급 없음"), Message.Samples[0].Confidence, EDCTConfidence::None);

	TestTrue(TEXT("구간 순서가 거꾸로, 숫자 문자열, 모르는 등급"), DCTMessageParser::ParseMessage(TEXT(R"({"type":"sample","sensorId":"A","value":24.6,"unit":"degC","quality":"good","ts":"2026-10-15T09:00:01.000Z","lower":26.0,"upper":"25.0","confidence":"great"})"), Message, Error));
	TestFalse(TEXT("틀린 구간은 받지 않는다"), Message.Samples[0].Lower.IsSet());
	TestEqual(TEXT("모르는 등급은 없음"), Message.Samples[0].Confidence, EDCTConfidence::None);
	TestEqual(TEXT("값은 그대로"), Message.Samples[0].Value.Get(0.0), 24.6);

	// 표현: 구간이 좁을수록 막대가 길고, 등급마다 색이 다르다. 등급이 없으면 막대를 숨긴다(0).
	FDCTSensorSample Sample;
	TestEqual(TEXT("등급 없으면 숨김"), DCTConfidence::BarFraction(Sample), 0.0);
	Sample.Confidence = EDCTConfidence::Ok;
	Sample.Lower = 24.0;
	Sample.Upper = 24.0;
	TestEqual(TEXT("구간 폭 0은 가장 길다"), DCTConfidence::BarFraction(Sample), 1.0);
	Sample.Upper = 26.0;
	TestEqual(TEXT("폭 2도는 절반"), DCTConfidence::BarFraction(Sample, 4.0), 0.5);
	Sample.Upper = 40.0;
	TestEqual(TEXT("아주 넓으면 최소"), DCTConfidence::BarFraction(Sample, 4.0, 0.15), 0.15);
	Sample.Lower.Reset();
	TestEqual(TEXT("구간 없이 등급만 있으면 최소"), DCTConfidence::BarFraction(Sample, 4.0, 0.15), 0.15);
	TestTrue(TEXT("등급 색이 서로 다르다"),
		!DCTConfidence::ColorFor(EDCTConfidence::Ok).Equals(DCTConfidence::ColorFor(EDCTConfidence::Caution))
		&& !DCTConfidence::ColorFor(EDCTConfidence::Caution).Equals(DCTConfidence::ColorFor(EDCTConfidence::Low))
		&& !DCTConfidence::ColorFor(EDCTConfidence::Low).Equals(DCTConfidence::ColorFor(EDCTConfidence::Fallback)));
	TestEqual(TEXT("등급 문자열 왕복"), DCTConfidenceFromString(DCTConfidenceToString(EDCTConfidence::Low)), EDCTConfidence::Low);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
