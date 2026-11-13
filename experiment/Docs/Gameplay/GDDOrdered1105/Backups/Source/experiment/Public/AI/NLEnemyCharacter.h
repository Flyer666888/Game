#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "AI/NLEnemyTypes.h"
#include "NLEnemyCharacter.generated.h"

class UNLEnemyBrainComponent;
class UNLCombatIdentityComponent;
class UNLCombatVitalsComponent;
class UNLBladeComponent;
class UNLTalismanAttackComponent;
class UNLAttackDefinition;
class UStaticMeshComponent;
class UTextRenderComponent;
class UAnimationAsset;
class UAnimSequenceBase;
class USkeletalMesh;
class UCurveVector;

/** Grounded enemy presentation shared by sword disciples and talisman casters. */
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
    virtual void SetCombatEnabled(bool bEnabled);
    UFUNCTION(BlueprintPure, Category="Combat|Enemy")
    bool IsCombatEnabled() const;
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
    virtual void SetLabPaused(bool bPaused);
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
    virtual void ResetForEncounter();
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy|Animation")
    void BeginAnimationAttackWindow(UAnimSequenceBase* Animation);
    UFUNCTION(BlueprintCallable, Category="Combat|Enemy|Animation")
    void EndAnimationAttackWindow(UAnimSequenceBase* Animation);
    bool IsInReaction() const;
    bool NativeIsLabPaused() const { return bLabPaused; }
    bool IsDeathPresentationInProgress() const { return bDeathPresentationPending || bPlayingDeath; }

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UNLCombatIdentityComponent> CombatIdentity;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UNLCombatVitalsComponent> Vitals;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UNLBladeComponent> Blade;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UNLTalismanAttackComponent> TalismanAttack;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UStaticMeshComponent> Sword;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy")
    TObjectPtr<UTextRenderComponent> StatusText;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Appearance")
    TObjectPtr<USkeletalMesh> EnemySkeletalMesh;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Appearance")
    bool bShowSword = true;
    /** An authored enemy definition takes precedence over the blade's existing definition. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy")
    TObjectPtr<UNLAttackDefinition> EnemyAttackDefinition;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Grip")
    FTransform SwordGripTransform;
    /** Hand bone or socket in this enemy's authored skeleton. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Grip")
    FName SwordAttachBone = FName(TEXT("hand_r"));
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
    /** Planar root travel removed from AttackAnimation, in actor-local cm at animation seconds.
     *  Optional: the capsule sweeps this travel while the animation retains the body's local motion. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UCurveVector> AttackRootMotionCurve;
    /** Optional caster one-shot. A caster without it keeps the planted idle pose during its warning. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimSequenceBase> CastAnimation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimSequenceBase> HitReactionAnimation;
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation")
    TObjectPtr<UAnimSequenceBase> DeathAnimation;
    /** Speed represented by one authored walk cycle, independent of navigation speed. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Animation", meta=(ClampMin="1.0"))
    float WalkAnimationSpeed = 122.815f;
protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    friend struct FNLAttackRootMotionTestAccess;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy", meta=(AllowPrivateAccess="true"))
    TObjectPtr<UNLEnemyBrainComponent> EnemyBrain;
    UPROPERTY(Transient)
    TObjectPtr<UAnimationAsset> CurrentLoopAnimation;
    UPROPERTY(Transient)
    TObjectPtr<UAnimSequenceBase> PendingDeathAnimation;
    UPROPERTY(Transient)
    TObjectPtr<UAnimationAsset> PendingPlaybackAnimation;
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
    void QueuePlayback(UAnimationAsset* Animation, bool bLoop, float Rate, float BlendSeconds);
    void StartPendingPlayback();
    void UpdateGroundedPresentation(float DeltaSeconds);
    void UpdateWalkPresentation(float DeltaSeconds);
    void BeginAttackRootMotion();
    void UpdateAttackRootMotion();
    void ClearAttackRootMotion();
    void ApplyGripMorph();
    void ClearAnimationAttackWindow();
    void UpdateStatus();
    FTransform InitialActorTransform;
    FTransform RestMeshTransform;
    float LastObservedHealth = 30.0f;
    double AnimationEndGameTime = 0.0;
    double LabPauseBeganGameTime = 0.0;
    double PlaybackRequestedGameTime = 0.0;
    float PendingPlaybackRate = 1.0f;
    float PendingBlendSeconds = .16f;
    float SmoothedWalkRate = 1.0f;
    double SmoothedMeshFloorZ = 0.0;
    FVector LastAttackRootMotionOffset = FVector::ZeroVector;
    FQuat AttackRootMotionFacing = FQuat::Identity;
    float LastAttackRootMotionTime = 0.0f;
    bool bAttackRootMotionActive = false;
    bool bAttackRootMotionFacingLocked = false;
    bool bPendingPlaybackLoop = false;
    bool bHasPendingPlayback = false;
    bool bHasPresentedAnimation = false;
    bool bGroundPresentationInitialized = false;
    bool bWalkPresentationMoving = false;
    bool bPlayingHit = false;
    bool bPlayingDeath = false;
    bool bDeathPresentationPending = false;
    bool bPlayingAttack = false;
    bool bAnimationAttackWindowOpen = false;
    bool bCombatEnabled = false;
    bool bLabPaused = false;
};
