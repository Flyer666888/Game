#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "Combat/NLCombatTypes.h"
#include "NLWeakPointComponent.generated.h"

/** A skull-sized zone follows the rendered head. The body capsule remains broad phase only. */
UCLASS(ClassGroup=(Combat), BlueprintType, meta=(BlueprintSpawnableComponent))
class EXPERIMENT_API UNLWeakPointComponent : public UActorComponent
{
	GENERATED_BODY()

public:
	UNLWeakPointComponent();

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|WeakPoint")
	bool bEnabled = true;

	/** None discovers the head/Head bone in either supported enemy skeleton. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|WeakPoint")
	FName HeadBoneName = NAME_None;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|WeakPoint", meta=(ClampMin="1.0", ClampMax="30.0", Units="cm"))
	float RadiusCm = 13.0f;

	/** Bone origins sit near the neck. This offset is in world centimetres, without bone scale. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|WeakPoint", meta=(ClampMin="-20.0", ClampMax="20.0", Units="cm"))
	float CenterHeightOffsetCm = 7.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat|WeakPoint", meta=(ClampMin="1.0", ClampMax="4.0"))
	float DamageMultiplier = 1.5f;

	UFUNCTION(BlueprintPure, Category="Combat|WeakPoint")
	bool HasWeakPoint() const;

	UFUNCTION(BlueprintPure, Category="Combat|WeakPoint")
	bool HasValidWeakPoint() const { return HasWeakPoint(); }

	UFUNCTION(BlueprintPure, Category="Combat|WeakPoint")
	FVector GetWeakPointCenter() const;

	UFUNCTION(BlueprintPure, Category="Combat|WeakPoint")
	FName GetWeakPointBone() const;

	/** Called only after resolver identity/guard/duplicate/protection checks. */
	bool MatchesPhysicalContact(const FNLCombatContact& Contact, AActor* SourceActor) const;

private:
	bool FindCenter(FVector& OutCenter) const;
};
