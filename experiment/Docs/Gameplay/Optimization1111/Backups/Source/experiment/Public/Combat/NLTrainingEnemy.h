#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "NLTrainingEnemy.generated.h"

class UAnimationAsset;
class UCapsuleComponent;
class UNLCombatIdentityComponent;
class UNLCombatVitalsComponent;
class USceneComponent;
class USkeletalMeshComponent;
class UTextRenderComponent;

/** Stationary practice target, with its actor origin on the floor. */
UCLASS(Blueprintable)
class EXPERIMENT_API ANLTrainingEnemy : public AActor
{
	GENERATED_BODY()

public:
	ANLTrainingEnemy();
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category="Combat|Training")
	void ResetForEncounter();

	/** Camera height references must ignore head motion during reactions and after death. */
	UFUNCTION(BlueprintPure, Category="Combat|Training")
	bool IsInReaction() const;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UCapsuleComponent> Body;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<USkeletalMeshComponent> EnemyMesh;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UNLCombatIdentityComponent> CombatIdentity;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UNLCombatVitalsComponent> Vitals;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UTextRenderComponent> StatusText;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UAnimationAsset> IdleAnimation;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UAnimationAsset> HitReactionAnimation;

	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Combat|Training")
	TObjectPtr<UAnimationAsset> DeathAnimation;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	UFUNCTION()
	void HandleVitalsChanged();

	UFUNCTION()
	void HandleDied();

	void StartIdle();
	bool StartReaction(UAnimationAsset* Animation, bool bDeathReaction);
	void StartPendingDeathPresentation();
	UPROPERTY(Transient)
	TObjectPtr<UAnimationAsset> PendingDeathAnimation;
	FTransform RestMeshTransform = FTransform::Identity;
	double ReactionFinishGameTime = 0.0;
	float ActiveReactionLength = 0.0f;
	float LastObservedHealth = 0.0f;
	bool bHitReactionPlaying = false;
	bool bDeathAnimationPlaying = false;
	bool bDeathPresentationPending = false;
};
