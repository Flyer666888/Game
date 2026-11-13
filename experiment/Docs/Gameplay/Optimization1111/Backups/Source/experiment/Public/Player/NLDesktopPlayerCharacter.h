#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "NLDesktopPlayerCharacter.generated.h"

class UCameraComponent;
class UBoxComponent;
class USceneComponent;
class USkeletalMeshComponent;
class UStaticMesh;
class UStaticMeshComponent;
class UNLBladeComponent;
class UNLCombatIdentityComponent;
class UNLCombatVitalsComponent;
class UNLCombatRecoveryComponent;
class UNLAbilityComponent;
class UNLGuardComponent;
class UNLAttackDefinition;
class USoundBase;
class ANLEncounterController;
class ANLLevelEncounterDirector;
class ANLEnemyCharacter;
class ANLCombatProjectile;
struct FNLCombatResult;
struct FNLCheckpointSnapshot;

/** Grounded desktop control adapter for the Combat Lab. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLDesktopPlayerCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    ANLDesktopPlayerCharacter();
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|View")
    TObjectPtr<UCameraComponent> PlayerCamera;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Weapon")
    TObjectPtr<USkeletalMeshComponent> RightHand;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Weapon")
    TObjectPtr<UStaticMeshComponent> HeldWeapon;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Weapon")
    TObjectPtr<UStaticMeshComponent> RightSleeve;

    /** Anatomical midpoint between the eyes, in the preview enemy head's local space. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|View")
    FVector EnemyEyeOffset = FVector(0.0, -8.5, 8.0);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|View")
    float StandingEyeHeight = 161.0f;

    /** Current desktop sword disciple baseline, used before the first wave spawns. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|View", meta=(ClampMin="1.0"))
    float InitialEncounterEyeHeight = 146.81583f;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Combat")
    TObjectPtr<UNLBladeComponent> Blade;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Combat")
    TObjectPtr<UNLCombatIdentityComponent> CombatIdentity;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Combat")
    TObjectPtr<UNLCombatVitalsComponent> Vitals;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Recovery")
    TObjectPtr<UNLCombatRecoveryComponent> CombatRecovery;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Abilities")
    TObjectPtr<UNLAbilityComponent> Abilities;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|View")
    bool bMatchEncounterEyeHeight = true;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Guard")
    TObjectPtr<UNLGuardComponent> Guard;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Guard")
    TObjectPtr<USceneComponent> MirrorPivot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Guard")
    TObjectPtr<UBoxComponent> GuardCollision;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Guard")
    TObjectPtr<UStaticMeshComponent> MirrorFace;

    /** Optional imported shield. If unset, the dragon shield asset is used when available. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|Guard|Visual")
    TObjectPtr<UStaticMesh> ShieldVisualMesh;

    /** Imported shield placement relative to the guard pivot; this never changes guard collision. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|Guard|Visual")
    FTransform ShieldVisualTransform = FTransform::Identity;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Guard|Visual")
    TObjectPtr<USkeletalMeshComponent> LeftHand;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Guard|Visual")
    TObjectPtr<UStaticMeshComponent> LeftSleeve;

    /** Shield-local wrist: maps the current 2.1cm sword grip onto the shield's horizontal rear handle. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|Guard|Visual")
    FTransform LeftHandGripTransform = FTransform(
        FQuat(0.0, 0.0, UE_INV_SQRT_2, UE_INV_SQRT_2),
        FVector(-12.96098, 0.0, 2.08902), FVector(1.0, -1.0, 1.0));

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Player|Combat")
    TObjectPtr<UNLAttackDefinition> BladeQiDefinition;

    /** Replace with a visual subclass later; contact and damage stay shared. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|SwordQi")
    TSubclassOf<ANLCombatProjectile> BladeQiProjectileClass;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|SwordQi", meta=(ClampMin="1.0", Units="cm/s"))
    float BladeQiSpeedCmPerSec = 1200.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|SwordQi", meta=(ClampMin="0.1", Units="cm"))
    float BladeQiRadiusCm = 5.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|SwordQi", meta=(ClampMin="1.0", Units="cm"))
    float BladeQiRangeCm = 4800.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Player|SwordQi", meta=(ClampMin="0.0", Units="cm"))
    float BladeQiMuzzleOffsetCm = 8.0f;

    /** Desktop development input; real VR swings must use tracked hand poses. */
    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    void StartDesktopSlash();

    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    void ToggleCombatPause();

    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    virtual void ResetLab();

    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    virtual void FireBladeQi();

    UFUNCTION(BlueprintCallable, Category="Player|Abilities")
    virtual void ActivatePulse();

    UFUNCTION(BlueprintCallable, Category="Player|Abilities")
    virtual void ActivateBurst();

    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    void RaiseMirror();

    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    void LowerMirror();

    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    void ToggleProjectileTraining();

    UFUNCTION(BlueprintCallable, Category="Player|Desktop")
    void ToggleSwordDuel();

    UFUNCTION(BlueprintPure, Category="Player|Encounter")
    virtual ANLEncounterController* GetEncounterController() const;

    /** Automatic region entry may wait for a control adapter without changing player life state. */
    UFUNCTION(BlueprintPure, Category="Player|Encounter")
    virtual bool IsReadyForLevelEncounter() const { return true; }

    float GetLastHitTimeSeconds() const { return LastHitTimeSeconds; }
    int32 GetSuccessfulHitCount() const { return SuccessfulHitCount; }
    bool IsDesktopSlashing() const { return bDesktopSlashing; }
    float GetLastBlockTimeSeconds() const { return LastBlockTimeSeconds; }
    float GetLastDamageTimeSeconds() const { return LastDamageTimeSeconds; }
    float GetBladeQiCooldownRemaining() const;
    bool IsProjectileTrainingEnabled() const;
    bool IsReflectionTrainingAvailable() const;
    bool HasLiveReflectionLauncher() const;
    bool HasSwordEnemies() const;
    bool IsSwordDuelEnabled() const;
    float GetLastParryTimeSeconds() const { return LastParryTimeSeconds; }
    int32 GetPerfectParryCount() const { return PerfectParryCount; }

    UFUNCTION(BlueprintPure, Category="Combat|WeakPoint")
    float GetLastWeakPointHitTimeSeconds() const { return LastWeakPointHitTimeSeconds; }

    UFUNCTION(BlueprintPure, Category="Combat|WeakPoint")
    float GetLastWeakPointMultiplier() const { return LastWeakPointMultiplier; }

    UFUNCTION(BlueprintPure, Category="Combat|WeakPoint")
    int32 GetWeakPointHitCount() const { return WeakPointHitCount; }
    bool AreCheckpointsEnabled() const;
    bool IsCheckpointReady() const
    {
        return bCheckpointInitialized && !bCheckpointOperationInProgress && !bRestoringCheckpoint
            && (!AreCheckpointsEnabled() || CheckpointWaveIndex != INDEX_NONE);
    }
    FName GetCheckpointFailureReason() const { return CheckpointFailureReason; }
    bool IsRestoringCheckpoint() const { return bRestoringCheckpoint; }
    bool HasCheckpointFailure() const { return !CheckpointFailureReason.IsNone(); }
    int32 GetCheckpointWaveNumber() const { return CheckpointWaveIndex + 1; }
    int32 GetCheckpointRetryCount() const { return CheckpointRetryCount; }
    FString GetCheckpointStatusMessage() const;
    FString GetCheckpointFailureMessage() const;

protected:
    virtual void BeginPlay() override;
    virtual bool UsesTrackedVRControls() const { return false; }
    virtual void ResetWeaponPose();
    virtual void OnSpatialStateRestored() {}
    /** Shared level retry for desktop and tracked controls; laboratory resets remain separate. */
    bool RestoreLevelStage(ANLLevelEncounterDirector* Director, const FTransform& InitialSafeTransform,
        FName* OutFailureReason = nullptr);
    virtual FTransform GetBladeQiOriginTransform() const;
    /** Shared launch path; the VR adapter calls this only after gesture gating. */
    bool TryLaunchBladeQi();

    /** Optional future presentation hook; no VFX are required by the template. */
    UFUNCTION(BlueprintImplementableEvent, Category="Player|SwordQi")
    void OnBladeQiLaunched(ANLCombatProjectile* Projectile);

private:
    void LookYaw(float Value);
    void LookPitch(float Value);
    void MatchEnemyEyeHeight();
    void UpdateDesktopSlash(float DeltaSeconds);
    void UpdateSleeve();
    void InitializeCheckpoints();
    bool CaptureWaveEntryCheckpoint(int32 WaveIndex);
    bool RestoreCheckpoint(bool bCountRetry);
    bool ApplyCheckpointSnapshot(const FNLCheckpointSnapshot& Snapshot, bool bCountRetry);
    bool ValidateCheckpointForEncounter(const FNLCheckpointSnapshot& Snapshot, FName& OutReason) const;
    void LockCheckpointInputs();
    void FailCheckpointRestore(FName Reason);
    void ClearEyeHeightReference();
    void ResetCombatFeedback();

    UFUNCTION()
    void HandleWaveEntryReady(int32 WaveIndex);

    UFUNCTION()
    void HandleEncounterEnemyDefeated(ANLEnemyCharacter* Enemy, FGuid EnemyRuntimeId, int32 SpawnOrdinal);

    UFUNCTION()
    void ReceiveCombatResult(const FNLCombatResult& Result);

    UFUNCTION()
    void HandlePlayerDied();

    TWeakObjectPtr<AActor> EyeHeightReference;
    mutable TWeakObjectPtr<ANLEncounterController> EncounterControllerCache;
    FVector RestHandLocation;
    FQuat RestHandRotation;
    FQuat SlashRaisedRotation;
    FQuat SlashEndRotation;
    FVector InitialPlayerLocation;
    FRotator InitialControlRotation;
    float SlashTimeSeconds = 0.0f;
    float LastHitTimeSeconds = -1000.0f;
    float LastBlockTimeSeconds = -1000.0f;
    float LastDamageTimeSeconds = -1000.0f;
    float LastParryTimeSeconds = -1000.0f;
    float LastWeakPointHitTimeSeconds = -1000.0f;
    float LastWeakPointMultiplier = 1.0f;
    int32 WeakPointHitCount = 0;
    float NextBladeQiTimeSeconds = 0.0f;
    int32 PerfectParryCount = 0;
    UPROPERTY(Transient)
    TObjectPtr<USoundBase> HitSound;
    UPROPERTY(Transient)
    TObjectPtr<USoundBase> BlockSound;
    UPROPERTY(Transient)
    TObjectPtr<USoundBase> ParrySound;
    int32 SuccessfulHitCount = 0;
    bool bDesktopSlashing = false;
    bool bDesktopViewportHadFocus = true;
    bool bUsingCustomShieldVisual = false;
    bool bStrikeRequested = false;
    bool bStrikeFinished = false;
    bool bCheckpointInitialized = false;
    bool bCheckpointOperationInProgress = false;
    bool bRestoringCheckpoint = false;
    uint8 CheckpointMovementMode = 0;
    uint8 CheckpointCustomMovementMode = 0;
    int32 CheckpointWaveIndex = INDEX_NONE;
    int32 CheckpointRetryCount = 0;
    FName CheckpointStatus = NAME_None;
    FName CheckpointFailureReason = NAME_None;
};
