#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Combat/NLCombatTypes.h"
#include "NLCombatIdentityComponent.generated.h"

UCLASS(ClassGroup=(Combat), BlueprintType, Blueprintable, meta=(BlueprintSpawnableComponent))
class experiment_API UNLCombatIdentityComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLCombatIdentityComponent();

	virtual void BeginPlay() override;

	UFUNCTION(BlueprintPure, Category="Combat|Identity")
	FGuid GetRuntimeId() const { return RuntimeId; }

	UFUNCTION(BlueprintCallable, Category="Combat|Identity")
	FGuid EnsureRuntimeId();

	UFUNCTION(BlueprintPure, Category="Combat|Identity")
	ENLCombatFaction GetFaction() const { return Faction; }

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Identity")
	ENLCombatFaction Faction = ENLCombatFaction::Neutral;

private:
	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category="Combat|Identity", meta=(AllowPrivateAccess="true"))
	FGuid RuntimeId;
};
