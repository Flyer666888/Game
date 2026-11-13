#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Combat/NLCombatTypes.h"
#include "NLGuardComponent.generated.h"

class UBoxComponent;
class UNLCombatVitalsComponent;
class USceneComponent;

/** Directional projectile barrier, separate from its visible mesh and the player's body. */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLGuardComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLGuardComponent();
	virtual void BeginPlay() override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

	UFUNCTION(BlueprintCallable, Category="Combat|Guard")
	void ConfigureGuard(UBoxComponent* Collision, USceneComponent* Visual);

	UFUNCTION(BlueprintCallable, Category="Combat|Guard")
	void SetGuardHeld(bool bHeld);

	UFUNCTION(BlueprintCallable, Category="Combat|Guard")
	void ResetGuard();

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	bool IsGuardActive() const;

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	bool IsGuardBroken() const;

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	bool IsWaitingForRelease() const { return bRequiresRelease; }

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	float GetGuard() const;

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	float GetMaxGuard() const;

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	float GetBreakRemainingSeconds() const;

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	bool IsPerfectWindowActive() const;

	UFUNCTION(BlueprintPure, Category="Combat|Guard")
	float GetPerfectWindowRemaining() const;

	/** Called by the resolver after validating attack identity and blockability. */
	bool TryBlockContact(const FNLCombatContact& Contact, float& OutGuardSpent);
	ENLCombatOutcome ResolveDefenseContact(const FNLCombatContact& Contact, bool bAllowPerfect, float& OutGuardSpent);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Guard")
	TObjectPtr<UBoxComponent> GuardCollision;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Guard")
	TObjectPtr<USceneComponent> GuardVisual;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0"))
	float BlockGuardCost = 12.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0"))
	float MeleeBlockGuardCost = 20.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|PerfectGuard", meta=(ClampMin="0.0"))
	float PerfectGuardCost = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|PerfectGuard", meta=(ClampMin="0.0"))
	float PerfectWindowSeconds = 0.18f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|PerfectGuard", meta=(ClampMin="0.0"))
	float ReleaseRearmSeconds = 0.12f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|PerfectGuard", meta=(ClampMin="0.0"))
	float MinimumPerfectRaiseInterval = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0"))
	float MaintenanceCostPerSecond = 6.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0"))
	float RecoveryDelaySeconds = 0.8f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0"))
	float RecoveryPerSecond = 25.0f;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0"))
	float GuardBreakSeconds = 1.2f;

	/** Box-local +X is the outward-facing barrier normal. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0", ClampMax="1.0"))
	float MinimumFacingDot = 0.15f;

	/** Tolerance for the projectile sphere touching just outside the box's surface. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Guard", meta=(ClampMin="0.0"))
	float ContactPadding = 6.0f;

private:
	void BreakGuard();
	void SyncGuardPresentation();
	UNLCombatVitalsComponent* GetVitals() const;

	UPROPERTY(Transient)
	TObjectPtr<UNLCombatVitalsComponent> Vitals;

	double LastReleasedGameTime = 0.0;
	double LastUpdateGameTime = 0.0;
	double BreakEndsGameTime = 0.0;
	double PerfectWindowEndsGameTime = 0.0;
	double LastPerfectRaiseGameTime = 0.0;
	bool bGuardHeld = false;
	bool bGuardBroken = false;
	bool bRequiresRelease = false;
	bool bPerfectWindowAvailable = false;
	bool bFirstPerfectRaiseAllowed = true;
};
