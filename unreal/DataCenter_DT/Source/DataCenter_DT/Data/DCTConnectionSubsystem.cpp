#include "Data/DCTConnectionSubsystem.h"

#include "Async/Async.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "HAL/IConsoleManager.h"
#include "HttpModule.h"
#include "Interfaces/IHttpRequest.h"
#include "Interfaces/IHttpResponse.h"
#include "IWebSocket.h"
#include "WebSocketsModule.h"

namespace
{
	const TCHAR* StateName(EDCTConnectionState State)
	{
		switch (State)
		{
		case EDCTConnectionState::LoadingManifest: return TEXT("센서 목록 받는 중");
		case EDCTConnectionState::Connecting: return TEXT("접속 중");
		case EDCTConnectionState::Connected: return TEXT("연결됨");
		default: return TEXT("끊김");
		}
	}

	// http://호스트:포트 -> ws://호스트:포트/ws
	FString ToWebSocketUrl(const FString& BaseUrl)
	{
		FString Url = BaseUrl;
		Url.RemoveFromEnd(TEXT("/"));
		if (Url.StartsWith(TEXT("https://"))) Url = TEXT("wss://") + Url.RightChop(8);
		else if (Url.StartsWith(TEXT("http://"))) Url = TEXT("ws://") + Url.RightChop(7);
		return Url + TEXT("/ws");
	}

	UDCTConnectionSubsystem* FromWorld(UWorld* World)
	{
		UGameInstance* GameInstance = World ? World->GetGameInstance() : nullptr;
		return GameInstance ? GameInstance->GetSubsystem<UDCTConnectionSubsystem>() : nullptr;
	}

	// 0보다 크면 그 초마다 연결 상태를 로그에 쓴다(화면 없이 동작을 확인할 때 쓴다)
	TAutoConsoleVariable<float> CVarStatusLogSeconds(TEXT("dct.StatusLogSeconds"), 0.0f, TEXT("0보다 크면 이 간격(초)으로 게이트웨이 연결 상태를 로그에 쓴다."));

	FAutoConsoleCommandWithWorldAndArgs GConnectCommand(
		TEXT("dct.connect"), TEXT("게이트웨이에 연결한다. 예: dct.connect http://127.0.0.1:8080"),
		FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args, UWorld* World)
		{
			if (UDCTConnectionSubsystem* Subsystem = FromWorld(World))
			{
				Subsystem->Connect(Args.Num() > 0 ? Args[0] : TEXT("http://127.0.0.1:8080"));
			}
		}));

	FAutoConsoleCommandWithWorld GDisconnectCommand(
		TEXT("dct.disconnect"), TEXT("게이트웨이 연결을 끊는다."),
		FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
		{
			if (UDCTConnectionSubsystem* Subsystem = FromWorld(World))
			{
				Subsystem->Disconnect();
			}
		}));

	FAutoConsoleCommandWithWorld GStatusCommand(
		TEXT("dct.status"), TEXT("게이트웨이 연결 상태와 받은 값 개수를 로그에 쓴다."),
		FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
		{
			if (UDCTConnectionSubsystem* Subsystem = FromWorld(World))
			{
				UE_LOG(LogDCT, Display, TEXT("%s"), *Subsystem->DescribeStatus());
			}
		}));
}

void UDCTConnectionSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
}

void UDCTConnectionSubsystem::Deinitialize()
{
	if (State != EDCTConnectionState::Disconnected)
	{
		UE_LOG(LogDCT, Display, TEXT("종료 시 연결 상태: %s"), *DescribeStatus());
	}
	Disconnect();
	Super::Deinitialize();
}

void UDCTConnectionSubsystem::SetState(EDCTConnectionState NewState)
{
	if (State == NewState)
	{
		return;
	}
	State = NewState;
	UE_LOG(LogDCT, Log, TEXT("게이트웨이 연결 상태: %s"), StateName(State));
	OnConnectionStateChanged.Broadcast(State);
}

void UDCTConnectionSubsystem::Connect(const FString& InBaseUrl)
{
	Disconnect();
	BaseUrl = InBaseUrl;
	bWantConnected = true;
	RetryDelaySeconds = 2.0f;
	RequestManifest();
}

void UDCTConnectionSubsystem::Disconnect()
{
	bWantConnected = false;
	++ConnectionId; // 진행 중인 요청과 소켓의 콜백을 모두 무시한다
	CloseSocket();
	if (State != EDCTConnectionState::Disconnected)
	{
		SensorHub.MarkAllStale();
	}
	SetState(EDCTConnectionState::Disconnected);
}

void UDCTConnectionSubsystem::RequestManifest()
{
	SetState(EDCTConnectionState::LoadingManifest);
	const int32 MyId = ++ConnectionId;
	TWeakObjectPtr<UDCTConnectionSubsystem> WeakThis(this);

	TSharedRef<IHttpRequest, ESPMode::ThreadSafe> Request = FHttpModule::Get().CreateRequest();
	FString Url = BaseUrl;
	Url.RemoveFromEnd(TEXT("/"));
	Request->SetURL(Url + TEXT("/api/sensors"));
	Request->SetVerb(TEXT("GET"));
	Request->OnProcessRequestComplete().BindLambda([WeakThis, MyId](FHttpRequestPtr, FHttpResponsePtr Response, bool bOk)
	{
		AsyncTask(ENamedThreads::GameThread, [WeakThis, MyId, Body = (bOk && Response.IsValid() && Response->GetResponseCode() == 200) ? Response->GetContentAsString() : FString()]()
		{
			UDCTConnectionSubsystem* Self = WeakThis.Get();
			if (!Self || Self->ConnectionId != MyId || !Self->bWantConnected)
			{
				return;
			}
			TArray<FDCTSensorInfo> Sensors;
			FString Error;
			if (Body.IsEmpty())
			{
				Error = TEXT("센서 목록을 받지 못했다");
			}
			else
			{
				DCTMessageParser::ParseManifest(Body, Sensors, Error);
			}
			if (!Error.IsEmpty() || Sensors.IsEmpty())
			{
				UE_LOG(LogDCT, Warning, TEXT("센서 목록 오류: %s"), Error.IsEmpty() ? TEXT("센서가 0개") : *Error);
				Self->ScheduleReconnect();
				return;
			}
			UE_LOG(LogDCT, Log, TEXT("센서 목록 %d개를 받았다"), Sensors.Num());
			Self->SensorHub.Registry().Reset(MoveTemp(Sensors));
			Self->OpenSocket();
		});
	});
	Request->ProcessRequest();
}

void UDCTConnectionSubsystem::OpenSocket()
{
	SetState(EDCTConnectionState::Connecting);
	const int32 MyId = ++ConnectionId;
	TWeakObjectPtr<UDCTConnectionSubsystem> WeakThis(this);

	Socket = FWebSocketsModule::Get().CreateWebSocket(ToWebSocketUrl(BaseUrl));
	Socket->OnConnected().AddLambda([WeakThis, MyId]()
	{
		AsyncTask(ENamedThreads::GameThread, [WeakThis, MyId]()
		{
			UDCTConnectionSubsystem* Self = WeakThis.Get();
			if (Self && Self->ConnectionId == MyId)
			{
				Self->RetryDelaySeconds = 2.0f;
				Self->SetState(EDCTConnectionState::Connected);
			}
		});
	});
	Socket->OnConnectionError().AddLambda([WeakThis, MyId](const FString& Error)
	{
		AsyncTask(ENamedThreads::GameThread, [WeakThis, MyId, Error]()
		{
			UDCTConnectionSubsystem* Self = WeakThis.Get();
			if (Self && Self->ConnectionId == MyId)
			{
				UE_LOG(LogDCT, Warning, TEXT("WebSocket 오류: %s"), *Error);
				Self->CloseSocket();
				Self->SensorHub.MarkAllStale();
				Self->ScheduleReconnect();
			}
		});
	});
	Socket->OnClosed().AddLambda([WeakThis, MyId](int32 Code, const FString& Reason, bool)
	{
		AsyncTask(ENamedThreads::GameThread, [WeakThis, MyId, Code, Reason]()
		{
			UDCTConnectionSubsystem* Self = WeakThis.Get();
			if (Self && Self->ConnectionId == MyId)
			{
				UE_LOG(LogDCT, Log, TEXT("WebSocket 닫힘: %d %s"), Code, *Reason);
				Self->CloseSocket();
				Self->SensorHub.MarkAllStale();
				Self->ScheduleReconnect();
			}
		});
	});
	// 메시지는 어느 스레드에서 와도 큐에만 넣는다. 처리는 Tick(게임 스레드)에서 한다.
	Socket->OnMessage().AddLambda([this, MyId](const FString& Message)
	{
		if (ConnectionId == MyId)
		{
			Incoming.Enqueue(Message);
		}
	});
	Socket->Connect();
}

void UDCTConnectionSubsystem::CloseSocket()
{
	if (Socket.IsValid())
	{
		TSharedPtr<IWebSocket> Old = MoveTemp(Socket);
		Old->OnConnected().Clear();
		Old->OnConnectionError().Clear();
		Old->OnClosed().Clear();
		Old->OnMessage().Clear();
		if (Old->IsConnected())
		{
			Old->Close();
		}
	}
	FString Discard;
	while (Incoming.Dequeue(Discard)) {}
}

void UDCTConnectionSubsystem::ScheduleReconnect()
{
	if (!bWantConnected)
	{
		SetState(EDCTConnectionState::Disconnected);
		return;
	}
	SetState(EDCTConnectionState::Disconnected);
	NextRetryTime = FPlatformTime::Seconds() + RetryDelaySeconds;
	RetryDelaySeconds = FMath::Min(RetryDelaySeconds * 2.0f, 10.0f);
}

void UDCTConnectionSubsystem::DrainMessages()
{
	// 한 틱에 처리하는 양을 제한해서 한꺼번에 몰려도 프레임이 길어지지 않게 한다. 남은 것은 다음 틱에 처리한다.
	constexpr int32 MaxPerTick = 2000;
	FString Json;
	for (int32 Count = 0; Count < MaxPerTick && Incoming.Dequeue(Json); ++Count)
	{
		FDCTMessage Message;
		FString Error;
		if (DCTMessageParser::ParseMessage(Json, Message, Error))
		{
			++NumMessages;
			SensorHub.ApplyMessage(Message);
		}
		else if (++NumParseErrors <= 5)
		{
			UE_LOG(LogDCT, Warning, TEXT("메시지를 읽지 못했다(%s): %.120s"), *Error, *Json);
		}
	}
}

void UDCTConnectionSubsystem::Tick(float DeltaTime)
{
	DrainMessages();
	const float StatusInterval = CVarStatusLogSeconds.GetValueOnGameThread();
	if (StatusInterval > 0.0f && FPlatformTime::Seconds() >= NextStatusLogTime)
	{
		NextStatusLogTime = FPlatformTime::Seconds() + StatusInterval;
		UE_LOG(LogDCT, Display, TEXT("%s"), *DescribeStatus());
	}
	if (bWantConnected && State == EDCTConnectionState::Disconnected && FPlatformTime::Seconds() >= NextRetryTime)
	{
		// 센서 목록부터 다시 받는다(게이트웨이가 다시 시작되면 목록이 바뀌었을 수 있다)
		RequestManifest();
	}
}

FString UDCTConnectionSubsystem::DescribeStatus() const
{
	return FString::Printf(TEXT("상태: %s | 센서 %d개 | 받은 메시지 %d건 | 읽기 실패 %d건 | 목록에 없는 센서 %d건 | 알람 %d개(주의 %d, 위험 %d) | 시나리오: %s"),
		StateName(State), SensorHub.Registry().Num(), NumMessages, NumParseErrors, SensorHub.NumUnknownSensorDrops(),
		SensorHub.AlarmModel().ActiveSensors().Num(), SensorHub.AlarmModel().CountOf(EDCTAlarmState::Warn), SensorHub.AlarmModel().CountOf(EDCTAlarmState::Critical),
		SensorHub.CurrentScenario().IsEmpty() ? TEXT("없음") : *SensorHub.CurrentScenario());
}
