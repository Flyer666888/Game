#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "NLEnemyTypes.h"
#include "NLAttackDirectorSubsystem.generated.h"

/** Times use the world's paused combat clock; direction is expressed in world space. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLAttackSlotRequest
{
	GENERATED_BODY()

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	TObjectPtr<AActor> Attacker = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	TObjectPtr<AActor> Target = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	FGuid EnemyRuntimeId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	FName AttackDefinitionId = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	FGuid AttackInstanceId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	FGuid TargetRuntimeId;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	FVector AttackDirection = FVector::ForwardVector;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director", meta=(ClampMin="0.0"))
	float TelegraphSeconds = 0.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	double ProjectedImpactTime = 0.0;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director", meta=(ClampMin="0.0"))
	float ThreatWeight = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|Director")
	ENLAttackSlot Slot = ENLAttackSlot::Melee;
};

/** Bounded history stores IDs and actor names, without keeping actors alive. */
USTRUCT(BlueprintType)
struct EXPERIMENT_API FNLAttackDirectorDiagnostic
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	FName Reason = NAME_None;

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	FGuid ReservationId;

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	FNLAttackSlotRequest Request;

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	FString AttackerName;

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	FString TargetName;

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	double GameTime = 0.0;

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	double ExpiresAt = 0.0;

	UPROPERTY(BlueprintReadOnly, Category="Combat|Director|Diagnostics")
	bool bGranted = false;
};

USTRUCT()
struct FNLAttackReservation
{
	GENERATED_BODY()

	TWeakObjectPtr<AActor> Owner;
	TWeakObjectPtr<AActor> Target;
	FNLAttackSlotRequest Request;
	bool bStructuredRequest = false;
	ENLAttackSlot Slot = ENLAttackSlot::Melee;
	double ProjectedImpactTime = 0.0;
	double ExpiresAt = 0.0;
};

UCLASS()
class EXPERIMENT_API UNLAttackDirectorSubsystem : public UTickableWorldSubsystem
{
	GENERATED_BODY()

public:
	virtual void Tick(float DeltaTime) override;
	virtual TStatId GetStatId() const override;
	virtual bool IsTickableWhenPaused() const override { return false; }

	UFUNCTION(BlueprintCallable, Category="Combat|Director")
	bool TryRegisterActiveFighter(AActor* Fighter);

	UFUNCTION(BlueprintCallable, Category="Combat|Director")
	void UnregisterActiveFighter(AActor* Fighter);

	UFUNCTION(BlueprintCallable, Category="Combat|Director")
	bool TryAcquireAttackSlot(AActor* Attacker, ENLAttackSlot Slot, float ProjectedImpactDelay, FGuid& OutReservationId);

	UFUNCTION(BlueprintCallable, Category="Combat|Director")
	bool RequestAttackSlot(const FNLAttackSlotRequest& Request, FGuid& OutReservationId);

	UFUNCTION(BlueprintCallable, Category="Combat|Director")
	void ReleaseAttackSlot(FGuid ReservationId);

	UFUNCTION(BlueprintCallable, Category="Combat|Director")
	void CancelAttackSlot(FGuid ReservationId, FName Reason);

	UFUNCTION(BlueprintPure, Category="Combat|Director")
	bool IsReservationValid(FGuid ReservationId, AActor* ExpectedOwner = nullptr) const;

	UFUNCTION(BlueprintCallable, Category="Combat|Director")
	void ResetEncounter();

	UFUNCTION(BlueprintPure, Category="Combat|Director|Diagnostics")
	FString GetLastDiagnostic() const { return LastDiagnostic; }

	UFUNCTION(BlueprintPure, Category="Combat|Director|Diagnostics")
	FName GetReservationCancellationReason(FGuid ReservationId) const;

	UFUNCTION(BlueprintPure, Category="Combat|Director|Diagnostics")
	bool GetReservationRequest(FGuid ReservationId, FNLAttackSlotRequest& OutRequest, double& OutExpiresAt) const;

	UFUNCTION(BlueprintPure, Category="Combat|Director|Diagnostics")
	TArray<FNLAttackDirectorDiagnostic> GetRecentDiagnostics() const { return RecentDiagnostics; }

	UFUNCTION(BlueprintPure, Category="Combat|Director")
	int32 GetActiveFighterCount() const;

	UFUNCTION(BlueprintPure, Category="Combat|Director")
	int32 GetReservationCount() const;

private:
	void RemoveExpiredOrInvalidReservations();
	bool AllocateAttackSlot(const FNLAttackSlotRequest& Request, bool bStructuredRequest, FGuid& OutReservationId);
	FName GetInvalidReservationReason(const FNLAttackReservation& Reservation) const;
	int32 GetSlotCapacity(ENLAttackSlot Slot) const;
	void RecordDiagnostic(FName Reason, AActor* Owner, FGuid ReservationId = FGuid());
	void RecordCancellation(FGuid ReservationId, FName Reason, AActor* Owner);
	void RecordRequestDiagnostic(FName Reason, const FNLAttackSlotRequest& Request, FGuid ReservationId = FGuid(), double ExpiresAt = 0.0);

	UPROPERTY(EditDefaultsOnly, Category="Combat|Director", meta=(ClampMin="1"))
	int32 MaxActiveFighters = 12;

	UPROPERTY(EditDefaultsOnly, Category="Combat|Director", meta=(ClampMin="0.0"))
	float MinimumImpactSeparation = 0.7f;

	UPROPERTY(EditDefaultsOnly, Category="Combat|Director", meta=(ClampMin="0.1"))
	float ReservationTimeoutSeconds = 6.0f;

	TSet<TWeakObjectPtr<AActor>> ActiveFighters;
	TMap<FGuid, FNLAttackReservation> Reservations;
	TMap<FGuid, FName> CancellationReasons;
	TArray<FGuid> CancellationOrder;
	TArray<FNLAttackDirectorDiagnostic> RecentDiagnostics;
	FString LastDiagnostic;
};
