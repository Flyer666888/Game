#pragma once

#include "CoreMinimal.h"

/** One geometry definition drives both the visible crescent and its swept contact volume. */
namespace NLHorizontalSwordQi
{
    constexpr int32 SegmentCount = 16;
    constexpr float HalfWidthCm = 95.0f;
    constexpr float CurveDepthCm = 34.0f;
    constexpr float HalfHeightCm = 5.0f;

    inline FVector Point(float T)
    {
        return FVector(-CurveDepthCm * T * T, HalfWidthCm * T, 0.0f);
    }

    inline FVector Tangent(float T)
    {
        return FVector(-2.0f * CurveDepthCm * T, HalfWidthCm, 0.0f) * (2.0f / SegmentCount);
    }

    inline float HalfThickness(float T)
    {
        return FMath::Lerp(0.75f, 7.0f, 1.0f - T * T);
    }

    struct FSegment
    {
        FVector Start;
        FVector End;
        FVector Center;
        FVector Extent;
        FQuat Rotation;
    };

    inline FSegment Segment(int32 Index)
    {
        const float T0 = -1.0f + 2.0f * Index / SegmentCount;
        const float T1 = -1.0f + 2.0f * (Index + 1) / SegmentCount;
        FSegment Result;
        Result.Start = Point(T0);
        Result.End = Point(T1);
        Result.Center = (Result.Start + Result.End) * 0.5;
        Result.Rotation = (Result.End - Result.Start).Rotation().Quaternion();
        // Overlap adjacent sections slightly to avoid cracks in a fast swept arc.
        Result.Extent = FVector((Result.End - Result.Start).Size() * 0.5 + 0.5,
            FMath::Max(HalfThickness(T0), HalfThickness(T1)) + 0.5, HalfHeightCm);
        return Result;
    }
}

/** Rejects thrusts, vertical cuts and tiny fast jitters; accepts either horizontal cut direction. */
struct FNLHorizontalSwordQiGesture
{
    void Reset()
    {
        SwingId.Invalidate();
        TravelCm = 0.0f;
        DirectionSign = 0.0f;
    }

    bool Sample(const FGuid& CurrentSwing, const FVector& TipVelocity, const FVector& ViewRight,
        float SampleSeconds, bool bSwingActive, float MinimumLateralSpeed = 180.0f,
        float MinimumTravelCm = 10.0f)
    {
        if (!bSwingActive || !CurrentSwing.IsValid() || TipVelocity.ContainsNaN() || ViewRight.ContainsNaN()
            || !FMath::IsFinite(SampleSeconds) || SampleSeconds <= 0.0f || SampleSeconds > 0.1f
            || !FMath::IsFinite(MinimumLateralSpeed) || MinimumLateralSpeed <= 0.0f
            || !FMath::IsFinite(MinimumTravelCm) || MinimumTravelCm <= 0.0f)
        {
            Reset();
            return false;
        }
        const FVector Right = FVector(ViewRight.X, ViewRight.Y, 0.0f).GetSafeNormal();
        const float Lateral = FVector::DotProduct(TipVelocity, Right);
        const float Speed = TipVelocity.Size();
        if (Right.IsNearlyZero() || FMath::Abs(Lateral) < MinimumLateralSpeed
            || FMath::Abs(Lateral) < Speed * 0.60f || FMath::Abs(TipVelocity.Z) > FMath::Abs(Lateral) * 0.65f)
        {
            Reset();
            return false;
        }
        const float Sign = FMath::Sign(Lateral);
        if (CurrentSwing != SwingId || Sign != DirectionSign)
        {
            TravelCm = 0.0f;
            SwingId = CurrentSwing;
            DirectionSign = Sign;
        }
        TravelCm += FMath::Abs(Lateral) * SampleSeconds;
        return TravelCm >= MinimumTravelCm;
    }

private:
    FGuid SwingId;
    float TravelCm = 0.0f;
    float DirectionSign = 0.0f;
};
