#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimNotifies/AnimNotifyState.h"
#include "NLEnemyAttackWindowNotifyState.generated.h"

/** Author the sword damage interval on the animation; the brain must also grant it. */
UCLASS(meta=(DisplayName="NL Enemy Sword Attack Window"))
class EXPERIMENT_API UNLEnemyAttackWindowNotifyState : public UAnimNotifyState
{
    GENERATED_BODY()
public:
    UNLEnemyAttackWindowNotifyState();
    virtual FString GetNotifyName_Implementation() const override;
    virtual void NotifyBegin(USkeletalMeshComponent* MeshComp, UAnimSequenceBase* Animation,
        float TotalDuration, const FAnimNotifyEventReference& EventReference) override;
    virtual void NotifyEnd(USkeletalMeshComponent* MeshComp, UAnimSequenceBase* Animation,
        const FAnimNotifyEventReference& EventReference) override;
};
