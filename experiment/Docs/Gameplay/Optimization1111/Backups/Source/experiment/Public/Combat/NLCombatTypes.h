#pragma once

#include "CoreMinimal.h"
#include "NLCombatTypes.generated.h"

UENUM(BlueprintType)
enum class ENLCombatOutcome : uint8
{
	Hit,
	Blocked,
	PerfectParry,
	GuardBroken,
	RitualDamaged,
	Ignored
};

UENUM(BlueprintType)
enum class ENLCombatFaction : uint8
{
	Neutral,
	Player,
	Enemy,
	Objective,
	World
};

/** Narrow-phase evidence supplied by the real blade/projectile sweep. */
UENUM(BlueprintType)
enum class ENLContactSweepShape : uint8
{
	None,
	Sphere,
	Box
};

USTRUCT(BlueprintType)
struct FNLCombatContact
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadWrite)
	FGuid AttackInstanceId;

	UPROPERTY(BlueprintReadWrite)
	FGuid SourceRuntimeId;

	UPROPERTY(BlueprintReadWrite)
	FGuid TargetRuntimeId;

	// INDEX_NONE means this contact is not from a pooled projectile.
	UPROPERTY(BlueprintReadWrite)
	int32 ProjectileGeneration = INDEX_NONE;

	UPROPERTY(BlueprintReadWrite)
	double ContactTimeSeconds = 0.0;

	UPROPERTY(BlueprintReadWrite)
	FVector HitPosition = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite)
	FVector HitNormal = FVector::UpVector;

	UPROPERTY(BlueprintReadWrite)
	FVector IncomingVelocity = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite)
	FName AttackDefinitionId = NAME_None;

	UPROPERTY(BlueprintReadWrite)
	ENLContactSweepShape SweepShape = ENLContactSweepShape::None;

	/** A real point-motion sweep may classify inside the target's broad capsule. */
	UPROPERTY(BlueprintReadWrite)
	bool bAllowBodyInteriorProjection = false;

	UPROPERTY(BlueprintReadWrite)
	FVector SweepStart = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite)
	FVector SweepEnd = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite)
	float SweepRadiusCm = 0.0f;

	UPROPERTY(BlueprintReadWrite)
	FVector SweepBoxExtent = FVector::ZeroVector;

	UPROPERTY(BlueprintReadWrite)
	FQuat SweepOrientation = FQuat::Identity;
};

USTRUCT(BlueprintType)
struct FNLCombatResult
{
	GENERATED_BODY()

	UPROPERTY(BlueprintReadOnly)
	FGuid ResultId;

	UPROPERTY(BlueprintReadOnly)
	FGuid AttackInstanceId;

	UPROPERTY(BlueprintReadOnly)
	FGuid SourceRuntimeId;

	UPROPERTY(BlueprintReadOnly)
	FGuid TargetRuntimeId;

	UPROPERTY(BlueprintReadOnly)
	ENLCombatOutcome Outcome = ENLCombatOutcome::Ignored;

	UPROPERTY(BlueprintReadOnly)
	float AppliedDamage = 0.0f;

	/** Resolver-confirmed target metadata, used by resource rewards without guessing from actor names. */
	UPROPERTY(BlueprintReadOnly)
	ENLCombatFaction TargetFaction = ENLCombatFaction::Neutral;

	UPROPERTY(BlueprintReadOnly)
	bool bTargetDefeated = false;

	UPROPERTY(BlueprintReadOnly)
	float GuardSpent = 0.0f;

	UPROPERTY(BlueprintReadOnly)
	ENLCombatFaction NewProjectileFaction = ENLCombatFaction::Neutral;

	UPROPERTY(BlueprintReadOnly)
	FName FeedbackTag = NAME_None;

	UPROPERTY(BlueprintReadOnly)
	bool bWeakPointHit = false;

	UPROPERTY(BlueprintReadOnly)
	float WeakPointMultiplier = 1.0f;
};

struct FNLCombatHitKey
{
	FGuid AttackInstanceId;
	FGuid TargetRuntimeId;
	int32 ProjectileGeneration = INDEX_NONE;

	bool operator==(const FNLCombatHitKey& Other) const
	{
		return AttackInstanceId == Other.AttackInstanceId
			&& TargetRuntimeId == Other.TargetRuntimeId
			&& ProjectileGeneration == Other.ProjectileGeneration;
	}

	friend uint32 GetTypeHash(const FNLCombatHitKey& Key)
	{
		return HashCombine(
			HashCombine(GetTypeHash(Key.AttackInstanceId), GetTypeHash(Key.TargetRuntimeId)),
			GetTypeHash(Key.ProjectileGeneration));
	}
};
