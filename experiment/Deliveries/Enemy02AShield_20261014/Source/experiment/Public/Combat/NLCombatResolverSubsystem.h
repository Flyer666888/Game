#pragma once

#include "CoreMinimal.h"
#include "Subsystems/WorldSubsystem.h"
#include "Combat/NLCombatTypes.h"
#include "NLCombatResolverSubsystem.generated.h"

class AActor;
class UNLAttackDefinition;
class UNLGuardComponent;

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FNLCombatResultEvent, const FNLCombatResult&, Result);

UCLASS()
class EXPERIMENT_API UNLCombatResolverSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()

public:
	UFUNCTION(BlueprintCallable, Category="Combat|Resolve")
	FNLCombatResult ResolveContact(
		AActor* SourceActor,
		AActor* TargetActor,
		const FNLCombatContact& Contact,
		UNLAttackDefinition* AttackDefinition);

	/** Rejected shield contacts leave the attack eligible for subsequent body contact. */
	UFUNCTION(BlueprintCallable, Category="Combat|Resolve")
	FNLCombatResult ResolveGuardContact(
		AActor* SourceActor,
		AActor* TargetActor,
		const FNLCombatContact& Contact,
		UNLAttackDefinition* AttackDefinition,
		UNLGuardComponent* GuardComponent,
		bool bAllowReflection = false);

	UFUNCTION(BlueprintCallable, Category="Combat|Resolve")
	void ResetEncounterContacts();

	UPROPERTY(BlueprintAssignable, Category="Combat|Events")
	FNLCombatResultEvent OnCombatResult;

private:
	FNLCombatResult Publish(FNLCombatResult Result);

	// AttackInstanceId + target permits one sweep to hit several targets,
	// while suppressing repeated overlap notifications against each target.
	TSet<FNLCombatHitKey> ResolvedContacts;
};
