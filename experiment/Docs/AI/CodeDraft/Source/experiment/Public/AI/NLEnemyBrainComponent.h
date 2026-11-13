#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "NLEnemyTypes.h"
#include "NLEnemyBrainComponent.generated.h"

class AActor;
class AAIController;
class ACharacter;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FNLEnemyStateChanged, AActor*, Enemy, ENLEnemyState, PreviousState, ENLEnemyState, NewState);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FNLEnemyAttackWindow, AActor*, Enemy, AActor*, Target);

UCLASS(ClassGroup=(Combat), BlueprintType, Blueprintable, meta=(BlueprintSpawnableComponent))
class experiment_API UNLEnemyBrainComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLEnemyBrainComponent();

	UFUNCTION(BlueprintCallable, Category="Combat|Enemy")
	void StartBrain();

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

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy")
	ENLEnemyRole Role = ENLEnemyRole::SwordDisciple;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Movement", meta=(ClampMin="50.0"))
	float AttackRange = 180.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Timing", meta=(ClampMin="0.0"))
	float TelegraphSeconds = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Timing", meta=(ClampMin="0.05"))
	float AttackSeconds = 0.45f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Timing", meta=(ClampMin="0.0"))
	float RecoverSeconds = 1.1f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Movement", meta=(ClampMin="100.0"))
	float RepositionRadius = 350.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Enemy|Movement", meta=(ClampMin="1"))
	int32 MaxNavigationRetries = 3;

	UPROPERTY(BlueprintAssignable, Category="Combat|Enemy|Events")
	FNLEnemyStateChanged OnStateChanged;

	// The unified combat resolver should consume this event and decide whether a hit lands.
	UPROPERTY(BlueprintAssignable, Category="Combat|Enemy|Events")
	FNLEnemyAttackWindow OnAttackWindowStarted;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
	virtual void TickComponent(float DeltaTime, ELevelTick TickType, FActorComponentTickFunction* ThisTickFunction) override;

private:
	void SetState(ENLEnemyState NewState);
	void ReleaseReservation();
	void UpdateApproach(float DeltaTime);
	void UpdateWaitForSlot(float DeltaTime);
	void HandlePathFailure();
	bool TryReposition();
	ENLAttackSlot GetSlotForRole() const;
	ACharacter* GetCharacterOwner() const;
	AAIController* GetAIController() const;

	TWeakObjectPtr<AActor> TargetActor;
	TWeakObjectPtr<class UNLAttackDirectorSubsystem> AttackDirector;
	FGuid ReservationId;
	ENLEnemyState State = ENLEnemyState::Spawn;
	ENLEnemyState StateBeforePause = ENLEnemyState::Approach;
	float StateElapsed = 0.0f;
	float RetryElapsed = 0.0f;
	float ProgressCheckElapsed = 0.0f;
	float StaggerDuration = 0.0f;
	int32 NavigationRetries = 0;
	FVector LastProgressLocation = FVector::ZeroVector;
	bool bActiveRegistered = false;
	bool bMoveRequestActive = false;
};
