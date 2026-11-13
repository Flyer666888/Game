#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Animation/PoseSnapshot.h"
#include "NLDeathBlendAnimInstance.generated.h"

class USkeletalMeshComponent;

/** Single-node death playback with a short transition from the visible pose. */
UCLASS(Transient, NotBlueprintable)
class EXPERIMENT_API UNLDeathBlendAnimInstance : public UAnimSingleNodeInstance
{
    GENERATED_BODY()

public:
    UNLDeathBlendAnimInstance(const FObjectInitializer& ObjectInitializer);

    /** Captures before replacing the instance. Check switch safety before using a fallback. */
    static bool BeginOnMesh(USkeletalMeshComponent* Mesh, float DurationSeconds = .18f);

    /** A busy animation must be retried later, without switching to the fallback mode. */
    static bool CanSwitchAnimationInstance(const USkeletalMeshComponent* Mesh);

    const FPoseSnapshot& GetStartSnapshot() const { return StartSnapshot; }
    float GetBlendAlphaGameThread() const;

    /** Game-thread clock adjustment; evaluation reads the proxy copy, not this field. */
    void ShiftBlendStartAfterPause(double PauseDurationSeconds);

protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* InProxy) override;

private:
    UPROPERTY(Transient)
    FPoseSnapshot StartSnapshot;

    double BlendStartGameTime = 0.0;
    float BlendDurationSeconds = .18f;
};
