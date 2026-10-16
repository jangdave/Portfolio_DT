// 게이트웨이 연결: 센서 목록(GET /api/sensors)을 받고, WebSocket(/ws)에 접속해 메시지를 센서 허브에 반영한다 (docs/12 4장).
// 받은 메시지는 큐에 넣고 게임 스레드의 틱에서만 처리한다. 끊기면 마지막 값을 stale로 바꾸고 다시 연결한다.
//
// 콘솔 명령(Play 중): dct.connect [기본주소], dct.disconnect, dct.status
#pragma once

#include "CoreMinimal.h"
#include "Containers/Queue.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Tickable.h"
#include "Data/DCTSensorHub.h"
#include "DCTConnectionSubsystem.generated.h"

class IWebSocket;

enum class EDCTConnectionState : uint8
{
	Disconnected,
	LoadingManifest,
	Connecting,
	Connected,
};

UCLASS()
class DATACENTER_DT_API UDCTConnectionSubsystem : public UGameInstanceSubsystem, public FTickableGameObject
{
	GENERATED_BODY()

public:
	DECLARE_MULTICAST_DELEGATE_OneParam(FOnConnectionState, EDCTConnectionState);
	FOnConnectionState OnConnectionStateChanged;

	virtual void Initialize(FSubsystemCollectionBase& Collection) override;
	virtual void Deinitialize() override;

	// BaseUrl 예: http://127.0.0.1:8080 (WebSocket 주소는 ws://같은 호스트/ws로 만든다)
	void Connect(const FString& BaseUrl);
	void Disconnect();

	EDCTConnectionState GetState() const { return State; }
	FDCTSensorHub& Hub() { return SensorHub; }
	const FDCTSensorHub& Hub() const { return SensorHub; }
	FString DescribeStatus() const;

	// FTickableGameObject
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override { RETURN_QUICK_DECLARE_CYCLE_STAT(UDCTConnectionSubsystem, STATGROUP_Tickables); }
	virtual bool IsTickable() const override { return !IsTemplate(); }

private:
	void SetState(EDCTConnectionState NewState);
	void RequestManifest();
	void OpenSocket();
	void CloseSocket();
	void ScheduleReconnect();
	void DrainMessages();

	FDCTSensorHub SensorHub;
	EDCTConnectionState State = EDCTConnectionState::Disconnected;
	FString BaseUrl;
	bool bWantConnected = false;
	double NextRetryTime = 0.0;
	double NextStatusLogTime = 0.0;
	float RetryDelaySeconds = 2.0f;
	int32 ConnectionId = 0; // 오래된 콜백(이미 닫은 연결, 이전 요청)을 가려낸다

	TSharedPtr<IWebSocket> Socket;
	TQueue<FString, EQueueMode::Mpsc> Incoming;
	int32 NumMessages = 0;
	int32 NumParseErrors = 0;
};
