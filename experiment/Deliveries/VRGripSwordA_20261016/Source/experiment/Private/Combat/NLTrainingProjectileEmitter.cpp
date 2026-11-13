#include "Combat/NLTrainingProjectileEmitter.h"

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/TextRenderComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInterface.h"
#include "UObject/ConstructorHelpers.h"

ANLTrainingProjectileEmitter::ANLTrainingProjectileEmitter()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bTickEvenWhenPaused = false;
	SceneRoot = CreateDefaultSubobject<USceneComponent>(TEXT("SceneRoot"));
	SetRootComponent(SceneRoot);
	Body = CreateDefaultSubobject<UCapsuleComponent>(TEXT("Body"));
	Body->SetupAttachment(SceneRoot);
	Body->SetRelativeLocation(FVector(0.0, 0.0, 60.0));
	Body->InitCapsuleSize(22.0f, 60.0f);
	Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	Body->SetCollisionObjectType(ECC_Pawn);
	Body->SetCollisionResponseToAllChannels(ECR_Ignore);
	Body->SetCollisionResponseToChannel(ECC_Pawn, ECR_Block);
	Body->SetCollisionResponseToChannel(ECC_Visibility, ECR_Block);
	Body->SetCollisionResponseToChannel(ECC_GameTraceChannel2, ECR_Overlap);
	Body->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
	Body->SetGenerateOverlapEvents(false);
	Body->SetCanEverAffectNavigation(false);
	Visual = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Visual"));
	Visual->SetupAttachment(SceneRoot);
	Visual->SetRelativeLocation(FVector(0.0, 0.0, 55.0));
	Visual->SetRelativeScale3D(FVector(0.36, 0.36, 1.1));
	Visual->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Visual->SetCanEverAffectNavigation(false);
	Muzzle = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Muzzle"));
	Muzzle->SetupAttachment(SceneRoot);
	Muzzle->SetRelativeLocation(FVector(0.0, 0.0, 125.0));
	Muzzle->SetRelativeScale3D(FVector(0.14));
	Muzzle->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	Muzzle->SetCanEverAffectNavigation(false);
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Cylinder(
		TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
	static ConstructorHelpers::FObjectFinder<UStaticMesh> Sphere(
		TEXT("/Engine/BasicShapes/Sphere.Sphere"));
	if (Cylinder.Succeeded()) Visual->SetStaticMesh(Cylinder.Object);
	if (Sphere.Succeeded()) Muzzle->SetStaticMesh(Sphere.Object);
	CombatIdentity = CreateDefaultSubobject<UNLCombatIdentityComponent>(TEXT("CombatIdentity"));
	CombatIdentity->Faction = ENLCombatFaction::Enemy;
	Vitals = CreateDefaultSubobject<UNLCombatVitalsComponent>(TEXT("Vitals"));
	Vitals->MaxHealth = 60.0f;
	Vitals->Health = 60.0f;
	Vitals->DamageProtectionSeconds = 0.0f;
	StatusText = CreateDefaultSubobject<UTextRenderComponent>(TEXT("StatusText"));
	StatusText->SetupAttachment(SceneRoot);
	StatusText->SetRelativeLocation(FVector(0.0, 0.0, 155.0));
	StatusText->SetHorizontalAlignment(EHTA_Center);
	StatusText->SetVerticalAlignment(EVRTA_TextCenter);
	StatusText->SetWorldSize(9.0f);
	StatusText->SetText(FText::FromString(TEXT("F: ENABLE TRAINING")));
	StatusText->SetTextRenderColor(FColor(230, 220, 190));
	StatusText->SetCollisionEnabled(ECollisionEnabled::NoCollision);
	StatusText->SetCanEverAffectNavigation(false);
	Tags.Add(TEXT("NL_TrainingProjectileEmitter"));
}

void ANLTrainingProjectileEmitter::BeginPlay()
{
	Super::BeginPlay();
	if (UMaterialInterface* LauncherMaterial = LoadObject<UMaterialInterface>(nullptr,
		TEXT("/Game/ReversedScale/Combat/Materials/M_TrainingLauncher.M_TrainingLauncher")))
	{
		Visual->SetMaterial(0, LauncherMaterial);
	}
	if (UMaterialInterface* ShotMaterial = LoadObject<UMaterialInterface>(nullptr,
		TEXT("/Game/ReversedScale/Combat/Materials/M_EnemyShot.M_EnemyShot")))
	{
		Muzzle->SetMaterial(0, ShotMaterial);
	}
	Vitals->OnDied.AddDynamic(this, &ANLTrainingProjectileEmitter::HandleDied);
	SetFiringEnabled(false);
}

AActor* ANLTrainingProjectileEmitter::ResolveTarget() const
{
	return IsValid(TargetActor) ? TargetActor.Get() : UGameplayStatics::GetPlayerPawn(this, 0);
}

bool ANLTrainingProjectileEmitter::CanAttackTarget(AActor* Target) const
{
	if (!IsValid(Target) || Target == this || Target->GetWorld() != GetWorld()
		|| !IsValid(AttackDefinition) || AttackDefinition->StableId.IsNone() || Vitals->IsDead())
	{
		return false;
	}
	const UNLCombatVitalsComponent* TargetVitals = Target->FindComponentByClass<UNLCombatVitalsComponent>();
	return !TargetVitals || !TargetVitals->IsDead();
}

void ANLTrainingProjectileEmitter::SetFiringEnabled(bool bEnabled)
{
	bFiringEnabled = bEnabled && CanAttackTarget(ResolveTarget());
	bTelegraphing = false;
	TelegraphFireTime = 0.0;
	NextTelegraphTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0;
	LockedTargetPosition = FVector::ZeroVector;
	Muzzle->SetRelativeScale3D(FVector(0.14));
	UpdateStatus();
}

bool ANLTrainingProjectileEmitter::ToggleFiring()
{
	SetFiringEnabled(!bFiringEnabled);
	return bFiringEnabled;
}

void ANLTrainingProjectileEmitter::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	UWorld* World = GetWorld();
	if (!World || World->IsPaused()) return;
	if (bFiringEnabled)
	{
		AActor* Target = ResolveTarget();
		if (!CanAttackTarget(Target))
		{
			SetFiringEnabled(false);
		}
		else
		{
			const double Now = World->GetTimeSeconds();
			if (!bTelegraphing && Now >= NextTelegraphTime)
			{
				BeginTelegraph(Target, Now);
			}
			if (bTelegraphing)
			{
				const double Remaining = FMath::Max(0.0, TelegraphFireTime - Now);
				const float Progress = 1.0f - FMath::Clamp(static_cast<float>(Remaining / FMath::Max(0.05f, TelegraphSeconds)), 0.0f, 1.0f);
				Muzzle->SetRelativeScale3D(FVector(FMath::Lerp(0.14f, 0.26f, Progress)));
				if (Now >= TelegraphFireTime) FireProjectile(Now);
			}
		}
	}
	if (const APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0))
	{
		FVector CameraLocation;
		FRotator CameraRotation;
		PC->GetPlayerViewPoint(CameraLocation, CameraRotation);
		StatusText->SetWorldRotation((CameraLocation - StatusText->GetComponentLocation()).Rotation());
	}
}

void ANLTrainingProjectileEmitter::BeginTelegraph(AActor* Target, double Now)
{
	// Lock at telegraph start so movement can evade an announced projectile.
	LockedTargetPosition = Target->GetActorLocation() + TargetChestOffset;
	bTelegraphing = true;
	TelegraphFireTime = Now + FMath::Max(0.05f, TelegraphSeconds);
	UpdateStatus();
}

void ANLTrainingProjectileEmitter::FireProjectile(double Now)
{
	const FVector Origin = Muzzle->GetComponentLocation();
	FActorSpawnParameters Params;
	Params.Owner = this;
	Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	ANLCombatProjectile* Projectile = GetWorld()->SpawnActor<ANLCombatProjectile>(
		ANLCombatProjectile::StaticClass(), Origin, (LockedTargetPosition - Origin).Rotation(), Params);
	if (Projectile && !Projectile->InitializeProjectile(this, AttackDefinition,
		LockedTargetPosition - Origin, ProjectileSpeed, ProjectileRadius, ProjectileLifetime))
	{
		Projectile->Destroy();
	}
	bTelegraphing = false;
	Muzzle->SetRelativeScale3D(FVector(0.14));
	NextTelegraphTime = Now + FMath::Max(0.05f,
		FireIntervalSeconds - FMath::Max(0.05f, TelegraphSeconds));
	UpdateStatus();
}

void ANLTrainingProjectileEmitter::UpdateStatus()
{
	const TCHAR* Text = Vitals->IsDead() ? TEXT("DEFEATED")
		: bTelegraphing ? TEXT("INCOMING")
		: bFiringEnabled ? TEXT("TRAINING ACTIVE") : TEXT("F: ENABLE TRAINING");
	StatusText->SetText(FText::FromString(Text));
	StatusText->SetTextRenderColor(bTelegraphing ? FColor(255, 140, 80)
		: Vitals->IsDead() ? FColor(140, 215, 140) : FColor(230, 220, 190));
}

void ANLTrainingProjectileEmitter::HandleDied()
{
	SetFiringEnabled(false);
	Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void ANLTrainingProjectileEmitter::ResetForEncounter()
{
	SetFiringEnabled(false);
	Vitals->ResetVitals();
	Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
	UpdateStatus();
}
