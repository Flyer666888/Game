#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Save/NLCheckpointTypes.h"
#include "NLRitualObjective.generated.h"

class ANLRitualObjective;
class UBoxComponent;
class UNLAttackDefinition;
class UNLCombatIdentityComponent;
class UNLCombatVitalsComponent;
class USceneComponent;
class UStaticMeshComponent;
class UTextRenderComponent;

UENUM(BlueprintType)
enum class ENLRitualObjectiveState : uint8
{
    Inactive,
    Running,
    Paused,
    Interfered,
    Restoring,
    CompletionPending,
    Completed,
    Failed
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FNLRitualObjectiveEvent, ANLRitualObjective*, Objective);

/** Independent rescue target. All hostile damage still passes through the combat resolver. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLRitualObjective : public AActor
{
    GENERATED_BODY()

public:
    ANLRitualObjective();
    virtual void Tick(float DeltaSeconds) override;

    UFUNCTION(BlueprintCallable, Category="Objective|Ritual")
    bool InitializeObjective(FName InStableId, float InMaxIntegrity = 100.0f, float InEffectiveRescueSeconds = 240.0f);

    UFUNCTION(BlueprintCallable, Category="Objective|Ritual")
    void ResetForEncounter(bool bActivate = true);

    UFUNCTION(BlueprintCallable, Category="Objective|Ritual")
    void SetObjectiveActive(bool bActive);

    UFUNCTION(BlueprintCallable, Category="Objective|Ritual")
    void SetCombatPaused(bool bPaused);

    /** IDs identify authored sources; actor references are transient and never enter a save. */
    UFUNCTION(BlueprintCallable, Category="Objective|Ritual|Sources")
    bool RegisterInterferenceSource(FName SourceId, AActor* SourceActor);

    UFUNCTION(BlueprintCallable, Category="Objective|Ritual|Sources")
    bool UnregisterInterferenceSource(FName SourceId);

    UFUNCTION(BlueprintCallable, Category="Objective|Ritual|Sources")
    void ClearInterferenceSources();

    /** Only threats explicitly required by the encounter delay the rescue event after 100%. */
    UFUNCTION(BlueprintCallable, Category="Objective|Ritual|Sources")
    bool RegisterRemainingThreat(FName SourceId, AActor* SourceActor);

    UFUNCTION(BlueprintCallable, Category="Objective|Ritual|Sources")
    bool UnregisterRemainingThreat(FName SourceId);

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    ENLRitualObjectiveState GetObjectiveState() const;

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    float GetIntegrity() const;

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    float GetRescueProgress() const { return RescueProgress; }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    int32 GetInterferenceSourceCount() const { return InterferenceSources.Num(); }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    int32 GetRemainingThreatCount() const { return RemainingThreats.Num(); }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    bool IsRescueCompleted() const { return bCompleted; }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    bool IsFailureLocked() const { return bFailed; }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual")
    bool IsCompletionPending() const { return bCompletionPending; }

    /** The resolver calls this gate before consuming an attack/target contact. */
    UFUNCTION(BlueprintPure, Category="Objective|Ritual|Combat")
    bool CanReceiveAttack(AActor* SourceActor, UNLAttackDefinition* Definition) const;

    UFUNCTION(BlueprintPure, Category="Objective|Ritual|Combat")
    FName GetAttackRejectionReason(AActor* SourceActor, UNLAttackDefinition* Definition) const;

    UFUNCTION(BlueprintPure, Category="Objective|Ritual|Checkpoint")
    FNLObjectiveSnapshot CaptureObjectiveSnapshot() const;

    /** Restore scalars, clear transient references, then rebind live source IDs before FinishSourceRebuild. */
    UFUNCTION(BlueprintCallable, Category="Objective|Ritual|Checkpoint")
    bool RestoreObjectiveSnapshot(const FNLObjectiveSnapshot& Snapshot);

    /** Drops unbound saved IDs, so dead or absent casters cannot leave permanent interference. */
    UFUNCTION(BlueprintCallable, Category="Objective|Ritual|Checkpoint")
    int32 FinishSourceRebuild();

    UFUNCTION(BlueprintPure, Category="Objective|Ritual|Checkpoint")
    bool IsAwaitingSourceRebuild() const { return bAwaitingSourceRebuild; }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual|Diagnostics")
    FName GetLastFailureReason() const { return LastFailureReason; }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual|Diagnostics")
    int32 GetCompletionEventCount() const { return CompletionEventCount; }

    UFUNCTION(BlueprintPure, Category="Objective|Ritual|Diagnostics")
    int32 GetFailureEventCount() const { return FailureEventCount; }

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    FName ObjectiveStableId = TEXT("Objective.Ritual");

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Objective|Ritual", meta=(ClampMin="1.0"))
    float MaxIntegrity = 100.0f;

    /** GDD baseline: 240 effective combat seconds; interference and pause add no progress. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Objective|Ritual", meta=(ClampMin="1.0"))
    float EffectiveRescueSeconds = 240.0f;

    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    bool bStartActive = true;

    /** Explicitly authored enemy attack IDs. Empty means no attacks may harm the ritual. */
    UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Objective|Ritual|Combat")
    TArray<FName> AllowedAttackDefinitionIds;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    TObjectPtr<USceneComponent> SceneRoot;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    TObjectPtr<UBoxComponent> RitualBody;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    TObjectPtr<UStaticMeshComponent> RitualVisual;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    TObjectPtr<UTextRenderComponent> StatusText;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    TObjectPtr<UNLCombatIdentityComponent> CombatIdentity;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Objective|Ritual")
    TObjectPtr<UNLCombatVitalsComponent> Vitals;

    UPROPERTY(BlueprintAssignable, Category="Objective|Ritual|Events")
    FNLRitualObjectiveEvent OnObjectiveChanged;

    /** Encounter owner stops spawning later waves here, while required living threats remain. */
    UPROPERTY(BlueprintAssignable, Category="Objective|Ritual|Events")
    FNLRitualObjectiveEvent OnCompletionPending;

    UPROPERTY(BlueprintAssignable, Category="Objective|Ritual|Events")
    FNLRitualObjectiveEvent OnRescueCompleted;

    UPROPERTY(BlueprintAssignable, Category="Objective|Ritual|Events")
    FNLRitualObjectiveEvent OnObjectiveFailed;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
    UFUNCTION()
    void HandleVitalsChanged();

    UFUNCTION()
    void HandleSourceDied();

    UFUNCTION()
    void HandleSourceDestroyed(AActor* Actor);

    bool IsLiveEnemySource(AActor* Actor) const;
    bool IsLiveRequiredThreat(AActor* Actor) const;
    void BindSource(AActor* Actor);
    void UnbindUnusedSource(AActor* Actor);
    void PruneInvalidSources();
    void ClearAllSources();
    void FailObjective();
    void CompleteObjective();
    void RefreshPresentation();
    void BroadcastChanged();

    TMap<FName, TWeakObjectPtr<AActor>> InterferenceSources;
    TMap<FName, TWeakObjectPtr<AActor>> RemainingThreats;
    TSet<FName> ExpectedRestoredInterferenceIds;
    float RescueProgress = 0.0f;
    float LastObservedIntegrity = 100.0f;
    double LastRitualDamageGameTime = -1.0;
    uint64 CompletionCandidateFrame = 0;
    uint32 ResetGeneration = 0;
    bool bObjectiveActive = false;
    bool bCombatPaused = false;
    bool bCompletionPending = false;
    bool bCompleted = false;
    bool bFailed = false;
    bool bAwaitingSourceRebuild = false;
    bool bRestoringVitals = false;
    FName LastFailureReason = NAME_None;
    int32 CompletionEventCount = 0;
    int32 FailureEventCount = 0;
};
