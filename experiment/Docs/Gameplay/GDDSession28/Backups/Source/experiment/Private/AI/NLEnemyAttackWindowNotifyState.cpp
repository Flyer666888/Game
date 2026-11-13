#include "AI/NLEnemyAttackWindowNotifyState.h"

#include "AI/NLEnemyCharacter.h"
#include "Components/SkeletalMeshComponent.h"

UNLEnemyAttackWindowNotifyState::UNLEnemyAttackWindowNotifyState()
{
#if WITH_EDITORONLY_DATA
    bShouldFireInEditor = false;
    NotifyColor = FColor(255,130,70);
#endif
}

FString UNLEnemyAttackWindowNotifyState::GetNotifyName_Implementation() const
{
    return TEXT("NL Enemy Sword Attack Window");
}

void UNLEnemyAttackWindowNotifyState::NotifyBegin(USkeletalMeshComponent* MeshComp,
    UAnimSequenceBase* Animation, float TotalDuration, const FAnimNotifyEventReference& EventReference)
{
    Super::NotifyBegin(MeshComp,Animation,TotalDuration,EventReference);
    ANLEnemyCharacter* Enemy = MeshComp ? Cast<ANLEnemyCharacter>(MeshComp->GetOwner()) : nullptr;
    if (Enemy && MeshComp == Enemy->GetMesh())
    {
        Enemy->BeginAnimationAttackWindow(Animation);
    }
}

void UNLEnemyAttackWindowNotifyState::NotifyEnd(USkeletalMeshComponent* MeshComp,
    UAnimSequenceBase* Animation, const FAnimNotifyEventReference& EventReference)
{
    Super::NotifyEnd(MeshComp,Animation,EventReference);
    ANLEnemyCharacter* Enemy = MeshComp ? Cast<ANLEnemyCharacter>(MeshComp->GetOwner()) : nullptr;
    if (Enemy && MeshComp == Enemy->GetMesh())
    {
        Enemy->EndAnimationAttackWindow(Animation);
    }
}
