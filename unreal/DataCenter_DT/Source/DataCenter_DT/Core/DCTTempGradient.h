// 센서 값을 색으로 바꾼다 (docs/12 5장). 화면과 무관한 순수 계산이라 자동화 테스트로 검증한다.
#pragma once

#include "CoreMinimal.h"
#include "Core/DCTTypes.h"

namespace DCTTempGradient
{
	// 값을 파랑(Cold) - 초록 - 노랑 - 빨강(Hot) 순으로 바꾼다. 범위 밖은 양 끝 색으로 자른다.
	inline FLinearColor FromValue(double Value, double Cold, double Hot)
	{
		const double Span = FMath::Max(Hot - Cold, KINDA_SMALL_NUMBER);
		const float T = static_cast<float>(FMath::Clamp((Value - Cold) / Span, 0.0, 1.0));
		static const FLinearColor Stops[] = {
			FLinearColor(0.05f, 0.25f, 1.0f),  // 파랑
			FLinearColor(0.05f, 0.85f, 0.25f), // 초록
			FLinearColor(1.0f, 0.85f, 0.05f),  // 노랑
			FLinearColor(1.0f, 0.08f, 0.05f),  // 빨강
		};
		const float Scaled = T * 3.0f;
		const int32 Index = FMath::Min(static_cast<int32>(Scaled), 2);
		return FMath::Lerp(Stops[Index], Stops[Index + 1], Scaled - Index);
	}

	// 품질이 좋지 않으면 값 색 대신 상태 색을 쓴다. 값이 없으면 회색.
	inline FLinearColor ForSample(const FDCTSensorSample& Sample, double Cold, double Hot)
	{
		if (!Sample.Value.IsSet())
		{
			return FLinearColor(0.25f, 0.25f, 0.25f);
		}
		if (Sample.Quality == EDCTQuality::Bad)
		{
			return FLinearColor(0.8f, 0.0f, 0.8f); // 자홍: 범위 밖 값
		}
		if (Sample.Quality == EDCTQuality::Stale)
		{
			return FLinearColor(0.35f, 0.35f, 0.35f); // 회색: 오래된 값
		}
		return FromValue(Sample.Value.GetValue(), Cold, Hot);
	}
}
