#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "NLEnemyTypes.h"
#include "NLAttackDirectorSubsystem.generated.h"

USTRUCT()
struct FNLAttackReservation
{
	GENERATED_BODY()

	TWeakObjectPtr<AActor> Owner;
	ENLAttackSlot Slot = ENLAttackSlot::Melee;
	double ProjectedImpactTime = 0.0;
	double ExpiresAt = 0.0;
};

UCLASS()
class experiment_API UNLAttackDirectorSubsystem : public UTickableWorldSubsystem
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
	void ReleaseAttackSlot(FGuid ReservationId);

	UFUNCTION(BlueprintPure, Category="Combat|Director")
	int32 GetActiveFighterCount() const;

	UFUNCTION(BlueprintPure, Category="Combat|Director")
	int32 GetReservationCount() const { return Reservations.Num(); }

private:
	void RemoveExpiredOrInvalidReservations();
	int32 GetSlotCapacity(ENLAttackSlot Slot) const;

	UPROPERTY(EditDefaultsOnly, Category="Combat|Director", meta=(ClampMin="1"))
	int32 MaxActiveFighters = 12;

	UPROPERTY(EditDefaultsOnly, Category="Combat|Director", meta=(ClampMin="0.0"))
	float MinimumImpactSeparation = 0.7f;

	UPROPERTY(EditDefaultsOnly, Category="Combat|Director", meta=(ClampMin="0.1"))
	float ReservationTimeoutSeconds = 6.0f;

	TSet<TWeakObjectPtr<AActor>> ActiveFighters;
	TMap<FGuid, FNLAttackReservation> Reservations;
};
