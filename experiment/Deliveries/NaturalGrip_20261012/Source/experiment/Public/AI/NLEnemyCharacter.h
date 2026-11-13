#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AI/NLEnemyTypes.h"
#include "NLEnemyCharacter.generated.h"

class UNLEnemyBrainComponent;
class UNLCombatIdentityComponent;
class UNLCombatVitalsComponent;
class UNLBladeComponent;
class UStaticMeshComponent;
class UTextRenderComponent;
class UAnimationAsset;
class UAnimSequenceBase;
class USkeletalMesh;

/** Grounded sword disciple for the desktop combat slice. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLEnemyCharacter : public ACharacter
{
    GENERATED_BODY()
public:
    ANLEnemyCharacter();
    virtual void Tick(float DeltaSeconds) override;

    UFUNCTION(BlueprintPure, Category="Combat|Enemy")
    UNLEnemyBrainComponent* GetEnemyBrain() const { return EnemyBrain; }
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
    void SetCombatEnabled(bool bEnabled);
    UFUNCTION(BlueprintPure, Category="Combat|Enemy")
    bool IsCombatEnabled() const;
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
    void SetLabPaused(bool bPaused);
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
    void ResetForEncounter();
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy|Animation")
    void BeginAnimationAttackWindow(UAnimSequenceBase* Animation);
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy|Animation")
    void EndAnimationAttackWindow(UAnimSequenceBase* Animation);
    bool IsInReaction() const;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UNLCombatIdentityComponent> CombatIdentity;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UNLCombatVitalsComponent> Vitals;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UNLBladeComponent> Blade;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UStaticMeshComponent> Sword;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UTextRenderComponent> StatusText;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Appearance")
    TObjectPtr<USkeletalMesh> EnemySkeletalMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Grip")
    FTransform SwordGripTransform;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Grip")
    FName GripMorphName = FName(TEXT("EnemyGrip_R"));
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Grip", meta=(ClampMin="0.0", ClampMax="1.0"))
    float GripMorphWeight = 1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimationAsset> IdleAnimation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimationAsset> WalkAnimation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimSequenceBase> AttackAnimation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimSequenceBase> HitReactionAnimation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimSequenceBase> DeathAnimation;
protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy", meta=(AllowPrivateAccess="true"))
    TObjectPtr<UNLEnemyBrainComponent> EnemyBrain;
    UPROPERTY(Transient)
    TObjectPtr<UAnimationAsset> CurrentLoopAnimation;
    UPROPERTY(Transient)
    TObjectPtr<UAnimSequenceBase> PendingDeathAnimation;
    UFUNCTION()
    void HandleStateChanged(AActor* Enemy, ENLEnemyState PreviousState, ENLEnemyState NewState);
    UFUNCTION()
    void HandleAttackStarted(AActor* Enemy, AActor* Target);
    UFUNCTION()
    void HandleAttackEnded(AActor* Enemy, AActor* Target);
    UFUNCTION()
    void HandleAttackCancelled(AActor* Enemy, AActor* Target, FName Reason);
    UFUNCTION()
    void HandleVitalsChanged();
    UFUNCTION()
    void HandleDied();
    void PlayLoop(UAnimationAsset* Animation);
    void PlayOneShot(UAnimSequenceBase* Animation, bool bDeath, bool bAttack=false);
    void StartPendingDeathPresentation();
    void ApplyGripMorph();
    void ClearAnimationAttackWindow();
    void UpdateStatus();
    FTransform InitialActorTransform;
    FTransform RestMeshTransform;
    float LastObservedHealth = 30.0f;
    double AnimationEndGameTime = 0.0;
    bool bPlayingHit = false;
    bool bPlayingDeath = false;
    bool bDeathPresentationPending = false;
    bool bPlayingAttack = false;
    bool bAnimationAttackWindowOpen = false;
    bool bCombatEnabled = false;
};
