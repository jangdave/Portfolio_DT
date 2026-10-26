// 보정 모델(L2)의 신뢰 등급과 90% 구간을 화면 표현 값으로 바꾼다. 화면과 무관한 순수 계산이라 자동화 테스트로 검증한다.
// 색만으로 구분하지 않게 막대 길이도 함께 쓴다: 구간이 넓을수록 막대가 짧다(믿을 수 있는 정도가 낮을수록 작아 보인다).
#pragma once

#include "CoreMinimal.h"
#include "Core/DCTTypes.h"

namespace DCTConfidence
{
	inline FLinearColor ColorFor(EDCTConfidence Confidence)
	{
		switch (Confidence)
		{
		case EDCTConfidence::Ok: return FLinearColor(0.10f, 0.80f, 0.30f);       // 초록
		case EDCTConfidence::Caution: return FLinearColor(1.0f, 0.80f, 0.0f);    // 노랑
		case EDCTConfidence::Low: return FLinearColor(1.0f, 0.15f, 0.10f);       // 빨강
		case EDCTConfidence::Fallback: return FLinearColor(0.55f, 0.55f, 0.55f); // 회색: 보정하지 않은 값
		default: return FLinearColor(0.0f, 0.0f, 0.0f);
		}
	}

	// 막대 길이 비율(0~1). 구간 폭이 0이면 1, FullWidth(도) 이상이면 MinFraction. 등급이 없으면 0(막대를 숨긴다).
	inline double BarFraction(const FDCTSensorSample& Sample, double FullWidth = 4.0, double MinFraction = 0.15)
	{
		if (Sample.Confidence == EDCTConfidence::None)
		{
			return 0.0;
		}
		if (!Sample.Lower.IsSet() || !Sample.Upper.IsSet())
		{
			return MinFraction; // 등급만 있고 구간이 없으면 가장 짧게
		}
		const double Width = FMath::Max(Sample.Upper.GetValue() - Sample.Lower.GetValue(), 0.0);
		return FMath::Clamp(1.0 - Width / FMath::Max(FullWidth, KINDA_SMALL_NUMBER), MinFraction, 1.0);
	}
}
