// Copyright Epic Games, Inc. All Rights Reserved.

using UnrealBuildTool;

public class DataCenter_DT : ModuleRules
{
	public DataCenter_DT(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
	
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput" });

		// 게이트웨이 연결(HTTP, WebSocket)과 JSON 읽기 (Data 계층)
		PrivateDependencyModuleNames.AddRange(new string[] { "HTTP", "WebSockets", "Json" });

		// 3D 장면 연동(World 계층): USD Stage Actor에서 센서 앵커 컴포넌트를 찾는다
		PrivateDependencyModuleNames.AddRange(new string[] { "USDStage", "UnrealUSDWrapper" });

		// 소스 폴더를 모듈 기준 경로로 열어 "Core/DCTTypes.h" 형태로 포함한다
		PublicIncludePaths.Add(ModuleDirectory);

		// Uncomment if you are using Slate UI
		// PrivateDependencyModuleNames.AddRange(new string[] { "Slate", "SlateCore" });
		
		// Uncomment if you are using online features
		// PrivateDependencyModuleNames.Add("OnlineSubsystem");

		// To include OnlineSubsystemSteam, add it to the plugins section in your uproject file with the Enabled attribute set to true
	}
}
