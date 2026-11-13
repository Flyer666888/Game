#include "Combat/NLTrainingEnemy.h"

#include "Animation/AnimationAsset.h"
#include "Animation/AnimSequenceBase.h"
#include "Animation/NLDeathBlendAnimInstance.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "UObject/ConstructorHelpers.h"

ANLTrainingEnemy::ANLTrainingEnemy()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bTickEvenWhenPaused = false;
	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);

	Body = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Body"));
	Body->SetupAttachment(SceneRoot);
	Body->SetRelativeLocation(FVector(0.0, 0.0, 90.0));
	Body->InitCapsuleSize(27.0f, 90.0f);
	Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Body->SetCollisionObjectType(ECC_Pawn);
	Body->SetCollisionResponseToAllChannels(ECR_Ignore);
	Body->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
	Body->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
	Body->SetCollisionResponseToChannel(ECC_GameTraceChannel2, ECR_Overlap);
	Body->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
	Body->SetGenerateOverlapEvents(false);
	Body->SetCanEverAffectNavigation(false);

	EnemyMesh = CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("EnemyMesh"));
	EnemyMesh->SetupAttachment(SceneRoot);
	EnemyMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	EnemyMesh->SetCanEverAffectNavigation(false);
	EnemyMesh->PrimaryComponentTick.bTickEvenWhenPaused = false;
	EnemyMesh->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
	static ConstructorHelpers::FObjectFinder<USkeletalMesh> MeshAsset(
		TEXT("/Game/ReversedScale/Characters/WuxiaMale/SK_WuxiaMale_Feet.SK_WuxiaMale_Feet"));
	if (MeshAsset.Succeeded())
	{
		EnemyMesh->SetSkeletalMeshAsset(MeshAsset.Object);
	}
	static ConstructorHelpers::FObjectFinder<UAnimationAsset> IdleAsset(
		TEXT("/Game/ReversedScale/Characters/WuxiaMale/Animations/Wuxia_Idle_Planted.Wuxia_Idle_Planted"));
	if (IdleAsset.Succeeded())
	{
		IdleAnimation = IdleAsset.Object;
		EnemyMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
		EnemyMesh->SetAnimation(IdleAnimation);
		EnemyMesh->Play(true);
	}

	CombatIdentity = CreateDefaultSubobject<UNLCombatIdentityComponent>(TEXT("CombatIdentity"));
	CombatIdentity->Faction = ENLCombatFaction::Enemy;
	Vitals = CreateDefaultSubobject<UNLCombatVitalsComponent>(TEXT("Vitals"));
	Vitals->MaxHealth = 30.0f;
	Vitals->Health = 30.0f;
	Vitals->DamageProtectionSeconds = 0.0f;

	StatusText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("StatusText"));
	StatusText->SetupAttachment(SceneRoot);
	StatusText->SetRelativeLocation(FVector(0.0, 0.0, 195.0));
	StatusText->SetHorizontalAlignment(EHTA_Center);
	StatusText->SetVerticalAlignment(EVRTA_TextCenter);
	StatusText->SetWorldSize(6.0f);
	StatusText->SetTextRenderColor(FColor(245, 222, 180));
	StatusText->SetText(FText::FromString(TEXT("30 / 30")));
	StatusText->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	StatusText->SetCanEverAffectNavigation(false);

	Tags.Add(TEXT("NL_TrainingEnemy"));
	Tags.Add(TEXT("NL_EyeHeightReference"));
}

void ANLTrainingEnemy::BeginPlay()
{
	Super::BeginPlay();
	// Existing saved melee maps predate the projectile trace channel.
	Body->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
	RestMeshTransform = EnemyMesh->GetRelativeTransform();
	Vitals->OnVitalsChanged.AddDynamic(this, &ANLTrainingEnemy::HandleVitalsChanged);
	Vitals->OnDied.AddDynamic(this, &ANLTrainingEnemy::HandleDied);
	LastObservedHealth = Vitals->GetHealth();
	StartIdle();
	HandleVitalsChanged();
}

void ANLTrainingEnemy::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
	bDeathPresentationPending = false;
	PendingDeathAnimation = nullptr;
	Super::EndPlay(EndPlayReason);
}

void ANLTrainingEnemy::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UWorld* World = GetWorld();
	if (!World || World->IsPaused())
	{
		return;
	}
	if (bDeathPresentationPending)
	{
		StartPendingDeathPresentation();
	}

	if ((bHitReactionPlaying || bDeathAnimationPlaying)
		&& World->GetTimeSeconds() >= ReactionFinishGameTime)
	{
		if (bDeathAnimationPlaying)
		{
			// Stop retains the single-node pose; allow pose evaluation of the final position.
			EnemyMesh->SetPosition(ActiveReactionLength, false);
			EnemyMesh->Stop();
			bDeathAnimationPlaying = false;
		}
		else
		{
			StartIdle();
		}
	}

	if (const APlayerController* PlayerController = UGameplayStatics::GetPlayerController(this, 0))
	{
		FVector CameraLocation;
		FRotator CameraRotation;
		PlayerController->GetPlayerViewPoint(CameraLocation, CameraRotation);
		const FVector ViewDirection = CameraLocation - StatusText->GetComponentLocation();
		if (!ViewDirection.IsNearlyZero())
		{
			StatusText->SetWorldRotation(ViewDirection.Rotation());
		}
	}
}

void ANLTrainingEnemy::HandleVitalsChanged()
{
	const float CurrentHealth = Vitals->GetHealth();
	const bool bTookNonfatalDamage = CurrentHealth < LastObservedHealth && !Vitals->IsDead();
	LastObservedHealth = CurrentHealth;
	if (Vitals->IsDead())
	{
		StatusText->SetText(FText::FromString(TEXT("DEFEATED")));
		StatusText->SetTextRenderColor(FColor(140, 215, 140));
	}
	else
	{
		StatusText->SetText(FText::FromString(FString::Printf(TEXT("%.0f / %.0f"), Vitals->GetHealth(), Vitals->GetMaxHealth())));
		StatusText->SetTextRenderColor(FColor(245, 222, 180));
	}
	if (bTookNonfatalDamage)
	{
		StartReaction(HitReactionAnimation, false);
	}
}

void ANLTrainingEnemy::HandleDied()
{
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	bHitReactionPlaying = false;
	if (!StartReaction(DeathAnimation, true))
	{
		EnemyMesh->Stop();
	}
}

void ANLTrainingEnemy::StartIdle()
{
	bDeathPresentationPending = false;
	PendingDeathAnimation = nullptr;
	bHitReactionPlaying = false;
	bDeathAnimationPlaying = false;
	ReactionFinishGameTime = 0.0;
	ActiveReactionLength = 0.0f;
	EnemyMesh->bPauseAnims = false;
	EnemyMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	EnemyMesh->SetAnimation(IdleAnimation);
	EnemyMesh->SetPlayRate(1.0f);
	EnemyMesh->SetPosition(0.0f, false);
	EnemyMesh->Play(true);
}

bool ANLTrainingEnemy::StartReaction(UAnimationAsset* Animation, bool bDeathReaction)
{
	if (bDeathReaction)
	{
		bHitReactionPlaying = false;
		bDeathAnimationPlaying = false;
		bDeathPresentationPending = true;
		PendingDeathAnimation = Animation;
		ReactionFinishGameTime = 0.0;
		ActiveReactionLength = 0.0f;
		return true;
	}
	bDeathPresentationPending = false;
	PendingDeathAnimation = nullptr;
	const UAnimSequenceBase* Sequence = Cast<UAnimSequenceBase>(Animation);
	UWorld* World = GetWorld();
	if (!Sequence || !World || Sequence->GetPlayLength() <= KINDA_SMALL_NUMBER)
	{
		return false;
	}

	const float PlayRate = 1.0f;
	ActiveReactionLength = Sequence->GetPlayLength();
	ReactionFinishGameTime = World->GetTimeSeconds() + ActiveReactionLength / PlayRate;
	bHitReactionPlaying = !bDeathReaction;
	bDeathAnimationPlaying = bDeathReaction;
	EnemyMesh->bPauseAnims = false;
	EnemyMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	EnemyMesh->SetAnimation(Animation);
	EnemyMesh->SetPlayRate(PlayRate);
	EnemyMesh->SetPosition(0.0f, false);
	EnemyMesh->Play(false);
	return true;
}

void ANLTrainingEnemy::StartPendingDeathPresentation()
{
	UWorld* World = GetWorld();
	if (!bDeathPresentationPending || !World
		|| !UNLDeathBlendAnimInstance::CanSwitchAnimationInstance(EnemyMesh)) return;

	UAnimationAsset* Animation = PendingDeathAnimation;
	const UAnimSequenceBase* Sequence = Cast<UAnimSequenceBase>(Animation);
	bDeathPresentationPending = false;
	PendingDeathAnimation = nullptr;
	if (!Sequence || Sequence->GetPlayLength() <= KINDA_SMALL_NUMBER)
	{
		EnemyMesh->Stop();
		return;
	}

	ActiveReactionLength = Sequence->GetPlayLength();
	ReactionFinishGameTime = World->GetTimeSeconds() + ActiveReactionLength;
	bHitReactionPlaying = false;
	bDeathAnimationPlaying = true;
	EnemyMesh->bPauseAnims = false;
	if (!UNLDeathBlendAnimInstance::BeginOnMesh(EnemyMesh))
	{
		EnemyMesh->SetAnimationMode(EAnimationMode::AnimationSingleNode);
	}
	EnemyMesh->SetAnimation(Animation);
	EnemyMesh->SetPlayRate(1.0f);
	EnemyMesh->SetPosition(0.0f, false);
	EnemyMesh->Play(false);
	EnemyMesh->TickAnimation(0.0f, false);
	EnemyMesh->RefreshBoneTransforms();
}

bool ANLTrainingEnemy::IsInReaction() const
{
	return bHitReactionPlaying || (Vitals && Vitals->IsDead());
}

void ANLTrainingEnemy::ResetForEncounter()
{
	bDeathPresentationPending = false;
	PendingDeathAnimation = nullptr;
	bHitReactionPlaying = false;
	bDeathAnimationPlaying = false;
	ReactionFinishGameTime = 0.0;
	ActiveReactionLength = 0.0f;
	EnemyMesh->SetRelativeTransform(RestMeshTransform);
	EnemyMesh->SetHiddenInGame(false);
	Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Vitals->ResetVitals();
	LastObservedHealth = Vitals->GetHealth();
	StartIdle();
	HandleVitalsChanged();
}
