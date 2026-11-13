#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "NLEnemyCharacter.generated.h"

class UNLEnemyBrainComponent;

UCLASS(Blueprintable)
class experiment_API ANLEnemyCharacter : public ACharacter
{
	GENERATED_BODY()

public:
	ANLEnemyCharacter();

	UFUNCTION(BlueprintPure, Category="Combat|Enemy")
	UNLEnemyBrainComponent* GetEnemyBrain() const { return EnemyBrain; }

protected:
	virtual void BeginPlay() override;

private:
	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Enemy", meta=(AllowPrivateAccess="true"))
	TObjectPtr<UNLEnemyBrainComponent> EnemyBrain;
};
