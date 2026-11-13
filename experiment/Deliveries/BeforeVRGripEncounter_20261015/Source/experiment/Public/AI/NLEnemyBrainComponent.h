#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NLEnemyTypes.h"
#include "NLEnemyBrainComponent.generated.h"

class AActor;
class AAIController;
class ACharacter;
class UNLAttackDefinition;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FNLEnemyStateChanged, AActor*, Enemy, ENLEnemyState, PreviousState, ENLEnemyState, NewState);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FNLEnemyAttackWindow, AActor*, Enemy, AActor*, Target);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FNLEnemyAttackCancelled, AActor*, Enemy, AActor*, Target, FName, Reason);

UCLASS(ClassGroup=(Combat), BlueprintType, Blueprintable, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLEnemyBrainComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLEnemyBrainComponent();

	UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
	void StartBrain();

	/** Cancels old attacks and makes even a dead/despawned brain eligible to restart. Reset vitals first. */
	UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
	void ResetBrain();

	UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
	void SetCombatPaused(bool bPaused);

	UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
	void ApplyStagger(float DurationSeconds);

	UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
	void MarkDead();

	UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
	void Despawn();

	UFUNCTION(BlueprintPure, Category="Combat|Enemy")
	ENLEnemyState GetState() const { return State; }

	UFUNCTION(BlueprintPure, Category="Combat|Enemy")
	bool IsAttackWindowActive() const { return bAttackWindowActive; }

	UFUNCTION(BlueprintPure, Category="Combat|Enemy")
	FGuid GetAttackInstanceId() const { return CurrentAttackInstanceId; }

	/** Ranged aim is sampled once before Telegraph; it never follows the target during flight. */
	UFUNCTION(BlueprintPure, Category="Combat|Enemy|Ranged")
	FVector GetLockedAimPosition() const { return LockedAimPosition; }

	UFUNCTION(BlueprintPure, Category="Combat|Enemy|Ranged")
	AActor* GetLockedAimTarget() const { return LockedAimTarget.Get(); }

	/** Shares the actual casting hand origin with the ranged attack component. */
	UFUNCTION(BlueprintPure, Category="Combat|Enemy|Ranged")
	FVector GetRangedMuzzlePosition() const;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy")
	ENLEnemyRole Role = ENLEnemyRole::SwordDisciple;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Movement", meta=(ClampMin="50.0"))
	float AttackRange = 180.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Ranged", meta=(ClampMin="50.0"))
	float MinimumRangedDistance = 450.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Ranged", meta=(ClampMin="50.0"))
	float PreferredRangedDistance = 700.0f;

	/** Used by both the projectile and Director's projected impact time, in cm/s. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Ranged", meta=(ClampMin="1.0"))
	float ProjectileSpeed = 700.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Ranged")
	FVector TargetAimOffset = FVector(0.0f, 0.0f, 40.0f);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Ranged")
	FVector RangedMuzzleOffset = FVector(0.0f, 0.0f, 40.0f);

	/** Optional override; existing enemies continue to use their blade's authored definition. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Ranged")
	TObjectPtr<UNLAttackDefinition> RangedAttackDefinition = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Timing", meta=(ClampMin="0.0"))
	float SpawnGraceSeconds = 0.35f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Timing", meta=(ClampMin="0.0"))
	float TelegraphSeconds = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Timing", meta=(ClampMin="0.05"))
	float AttackSeconds = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Timing", meta=(ClampMin="0.0"))
	float RecoverSeconds = 1.1f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Movement", meta=(ClampMin="100.0"))
	float RepositionRadius = 350.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Movement", meta=(ClampMin="1"))
	int32 MaxNavigationRetries = 3;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Movement", meta=(ClampMin="10.0"))
	float RepositionAcceptanceDistance = 60.0f;

	UPROPERTY(BlueprintAssignable, Category="Combat|Enemy|Events")
	FNLEnemyStateChanged OnStateChanged;

	// The character opens its blade sweep, or releases one ranged projectile, in this window.
	UPROPERTY(BlueprintAssignable, Category="Combat|Enemy|Events")
	FNLEnemyAttackWindow OnAttackWindowStarted;

	UPROPERTY(BlueprintAssignable, Category="Combat|Enemy|Events")
	FNLEnemyAttackWindow OnAttackWindowEnded;

	UPROPERTY(BlueprintAssignable, Category="Combat|Enemy|Events")
	FNLEnemyAttackCancelled OnAttackWindowCancelled;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	void SetState(ENLEnemyState NewState);
	void ReleaseReservation(FName Reason = TEXT("Released"));
	void CancelAttackWindow(FName Reason);
	void FinishAttackWindow();
	void UpdateAttackTimeline();
	void StopNavigation();
	void HandleTargetLost();
	bool IsTargetUsable() const;
	bool IsOwnerDead() const;
	bool HasValidReservation() const;
	bool CheckNavigationProgress();
	void UpdateApproach(float DeltaTime);
	void UpdateWaitForSlot(float DeltaTime);
	void HandlePathFailure();
	bool TryReposition();
	bool TryRangedReposition();
	bool HasRangedLineOfSightTo(const FVector& AimPosition, AActor* AimTarget) const;
	bool ValidateRangedTelegraph();
	float GetRangedMinimumDistance() const;
	float GetRangedMaximumDistance() const;
	float GetRangedPreferredDistance() const;
	ENLAttackSlot GetSlotForRole() const;
	ACharacter* GetCharacterOwner() const;
	AAIController* GetAIController() const;

	TWeakObjectPtr<AActor> TargetActor;
	TWeakObjectPtr<AActor> LockedAimTarget;
	TWeakObjectPtr<class UNLAttackDirectorSubsystem> AttackDirector;
	FGuid ReservationId;
	FGuid CurrentAttackInstanceId;
	ENLEnemyState State = ENLEnemyState::Spawn;
	ENLEnemyState StateBeforePause = ENLEnemyState::Approach;
	float StateElapsed = 0.0f;
	float RetryElapsed = 0.0f;
	float ProgressCheckElapsed = 0.0f;
	float StaggerDuration = 0.0f;
	float NavigationMoveElapsed = 0.0f;
	float LockedTravelSeconds = 0.0f;
	int32 NavigationRetries = 0;
	FVector LastProgressLocation = FVector::ZeroVector;
	FVector RepositionDestination = FVector::ZeroVector;
	FVector LockedAimPosition = FVector::ZeroVector;
	bool bActiveRegistered = false;
	bool bMoveRequestActive = false;
	bool bRepositioning = false;
	bool bAttackWindowActive = false;
};
