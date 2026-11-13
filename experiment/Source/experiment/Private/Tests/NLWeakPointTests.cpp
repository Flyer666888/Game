#if WITH_DEV_AUTOMATION_TESTS

#include "AI/NLEnemyCharacter.h"
#include "AI/NLEnemyBrainComponent.h"
#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Combat/NLWeakPointComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/WorldSettings.h"
#include "Materials/Material.h"
#include "Math/RotationMatrix.h"
#include "Misc/AutomationTest.h"

namespace NLWeakPointTests
{
constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

struct FWorld
{
	UWorld* World = nullptr;
	AActor* Source = nullptr;
	ANLEnemyCharacter* Enemy = nullptr;
	UNLAttackDefinition* Attack = nullptr;
	uint64 SavedFrameCounter = GFrameCounter;

	FWorld()
	{
		if (!GEngine) return;
		const UWorld::InitializationValues Values = UWorld::InitializationValues().AllowAudioPlayback(false)
			.RequiresHitProxies(false).CreatePhysicsScene(true).ShouldSimulatePhysics(false)
			.EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
		World = UWorld::CreateWorld(EWorldType::Game, false,
			FName(*FString::Printf(TEXT("NilinWeakPoint_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits))),
			nullptr, true, ERHIFeatureLevel::Num, &Values);
		if (!World) return;
		GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
		World->InitializeActorsForPlay(FURL()); World->BeginPlay();
		if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();
		FActorSpawnParameters Params; Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		Source = World->SpawnActor<AActor>(FVector(-500, 0, 100), FRotator::ZeroRotator, Params);
		USceneComponent* Root = NewObject<USceneComponent>(Source);
		Source->AddInstanceComponent(Root); Source->SetRootComponent(Root); Root->RegisterComponent();
		UNLCombatIdentityComponent* Identity = NewObject<UNLCombatIdentityComponent>(Source);
		Identity->Faction = ENLCombatFaction::Player; Source->AddInstanceComponent(Identity); Identity->RegisterComponent();
		Identity->EnsureRuntimeId();
		UNLCombatVitalsComponent* Vitals = NewObject<UNLCombatVitalsComponent>(Source);
		Source->AddInstanceComponent(Vitals); Vitals->RegisterComponent();
		UClass* EnemyClass = LoadClass<ANLEnemyCharacter>(nullptr,
			TEXT("/Game/ReversedScale/Gameplay/V01/Enemies/BP_Level_sword.BP_Level_sword_C"));
		if (!EnemyClass) return;
		Enemy = World->SpawnActor<ANLEnemyCharacter>(EnemyClass, FVector(300, 0, 100), FRotator::ZeroRotator, Params);
		if (!Enemy) return;
		Enemy->SetCombatEnabled(true);
		Enemy->GetEnemyBrain()->SetComponentTickEnabled(false);
		Enemy->SetActorTickEnabled(false);
		Enemy->GetCharacterMovement()->DisableMovement();
		Enemy->GetMesh()->TickAnimation(0, false); Enemy->GetMesh()->RefreshBoneTransforms();
		Enemy->GetMesh()->SetComponentTickEnabled(false);
		Enemy->Vitals->MaxHealth = 100; Enemy->Vitals->DamageProtectionSeconds = 0; Enemy->Vitals->ResetVitals();
		Attack = NewObject<UNLAttackDefinition>(World);
		Attack->StableId = TEXT("Automation.WeakPoint.Physical"); Attack->Damage = 10;
		Attack->bCanBeBlocked = true; Attack->bCanBeParried = false; Attack->bCanBeReflected = false;
	}
	~FWorld()
	{
		if (World) { World->EndPlay(EEndPlayReason::Quit); GEngine->DestroyWorldContext(World); World->DestroyWorld(false); }
		GFrameCounter = SavedFrameCounter;
	}
	bool Ready() const { return World && Source && Enemy && Enemy->WeakPoint && Enemy->WeakPoint->HasValidWeakPoint() && Attack; }
	FVector Head() const { return Enemy->WeakPoint->GetWeakPointCenter(); }
	void Step(float Delta = .01f) { World->Tick(LEVELTICK_All, Delta); ++GFrameCounter; }

	ANLCombatProjectile* Fire(FVector Origin, bool bQi = false, float Speed = 300)
	{
		FActorSpawnParameters Params; Params.Owner = Source;
		Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		ANLCombatProjectile* Projectile = World->SpawnActor<ANLCombatProjectile>(Origin, FRotator::ZeroRotator, Params);
		if (!Projectile) return nullptr;
		Projectile->VisualMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
		if (bQi) Projectile->ConfigureHorizontalBladeQi();
		if (!Projectile->InitializeProjectile(Source, Attack, FVector::ForwardVector, Speed, 5, 2)) return nullptr;
		return Projectile;
	}
	float FireDamage(FVector Origin, bool bQi = false, float Speed = 300)
	{
		Enemy->Vitals->ResetVitals();
		ANLCombatProjectile* Projectile = Fire(Origin, bQi, Speed);
		if (!Projectile) return -1;
		for (int32 Index = 0; Index < 150 && IsValid(Projectile) && !Projectile->IsActorBeingDestroyed(); ++Index) Step();
		if (IsValid(Projectile) && !Projectile->IsActorBeingDestroyed()) Projectile->Destroy();
		return 100 - Enemy->Vitals->GetHealth();
	}
	FNLCombatContact Contact(bool bPhysical = true)
	{
		FNLCombatContact C;
		C.AttackInstanceId = FGuid::NewGuid(); C.AttackDefinitionId = Attack->StableId;
		C.SourceRuntimeId = Source->FindComponentByClass<UNLCombatIdentityComponent>()->EnsureRuntimeId();
		C.TargetRuntimeId = Enemy->CombatIdentity->EnsureRuntimeId();
		C.HitPosition = Head() + FVector(-28,0,0);
		C.SweepStart = Head() + FVector(-100,0,0); C.SweepEnd = Head() + FVector(100,0,0);
		C.SweepShape = bPhysical ? ENLContactSweepShape::Sphere : ENLContactSweepShape::None; C.SweepRadiusCm = 4;
		return C;
	}
	AActor* WallAt(FVector Location)
	{
		FActorSpawnParameters Params; Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
		AActor* Wall = World->SpawnActor<AActor>(Location, FRotator::ZeroRotator, Params);
		UBoxComponent* Box = NewObject<UBoxComponent>(Wall);
		Wall->AddInstanceComponent(Box); Wall->SetRootComponent(Box); Box->InitBoxExtent(FVector(1,100,100));
		Box->SetCollisionEnabled(ECollisionEnabled::QueryOnly); Box->SetCollisionObjectType(ECC_WorldStatic);
		Box->SetCollisionResponseToAllChannels(ECR_Ignore);
		Box->SetCollisionResponseToChannel(ECC_GameTraceChannel2,ECR_Block);
		Box->SetCollisionResponseToChannel(ECC_GameTraceChannel3,ECR_Block);
		Box->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
		Box->RegisterComponent(); Box->SetWorldLocation(Location);
		return Wall;
	}
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLWeakPointPhysicalProjectileTest,
	"Nilin.Combat.WeakPoint.RealMeshSphereAndCrescent", NLWeakPointTests::Flags)
bool FNLWeakPointPhysicalProjectileTest::RunTest(const FString& Parameters)
{
	NLWeakPointTests::FWorld F; if (!TestTrue(TEXT("Actual current sword mesh has a head bone"), F.Ready())) return false;
	const FVector Head = F.Head();
	TestEqual(TEXT("Slow sphere through head gains 1.5x at 100Hz"), F.FireDamage(Head-FVector(100,0,0)), 15.0f);
	TestEqual(TEXT("Fast sphere has the same multiplier"), F.FireDamage(Head-FVector(100,0,0),false,6000), 15.0f);
	TestEqual(TEXT("Torso sphere retains ordinary damage"), F.FireDamage(F.Enemy->GetActorLocation()-FVector(100,0,0)), 10.0f);
	TestEqual(TEXT("A capsule graze outside the skull is not a head shot"), F.FireDamage(Head+FVector(-100,25,0)), 10.0f);
	TestEqual(TEXT("Actual thin horizontal qi boxes can hit the skull at low speed"), F.FireDamage(Head-FVector(100,0,0),true), 15.0f);
	TestEqual(TEXT("Qi more than skull radius below the head remains a body hit"), F.FireDamage(Head+FVector(-100,0,-25),true), 10.0f);
	F.Enemy->WeakPoint->bEnabled = false;
	TestEqual(TEXT("Disabling head zone keeps ordinary contact"), F.FireDamage(Head-FVector(100,0,0)), 10.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLWeakPointContactGatesTest,
	"Nilin.Combat.WeakPoint.GatesDuplicateArmorAndMissingBone", NLWeakPointTests::Flags)
bool FNLWeakPointContactGatesTest::RunTest(const FString& Parameters)
{
	NLWeakPointTests::FWorld F; if (!TestTrue(TEXT("Real mesh fixture ready"), F.Ready())) return false;
	UNLCombatResolverSubsystem* R = F.World->GetSubsystem<UNLCombatResolverSubsystem>();
	FNLCombatContact C = F.Contact();
	const FNLCombatResult Head = R->ResolveContact(F.Source,F.Enemy,C,F.Attack);
	TestTrue(TEXT("A confirmed physical head hit sets its feedback"), Head.bWeakPointHit && Head.FeedbackTag==TEXT("Combat.WeakPoint.Head"));
	TestEqual(TEXT("Head damage is 15"),Head.AppliedDamage,15.0f);
	const FNLCombatResult Repeat = R->ResolveContact(F.Source,F.Enemy,C,F.Attack);
	TestTrue(TEXT("Duplicate emits no head reward"),Repeat.Outcome==ENLCombatOutcome::Ignored && !Repeat.bWeakPointHit);
	const FNLCombatResult Synthetic = R->ResolveContact(F.Source,F.Enemy,F.Contact(false),F.Attack);
	TestTrue(TEXT("Legacy synthetic contacts default to body"),!Synthetic.bWeakPointHit && Synthetic.AppliedDamage==10);
	F.Enemy->WeakPoint->HeadBoneName = TEXT("Missing.Automation.Bone");
	TestTrue(TEXT("Missing skull metadata disables zone"),!F.Enemy->WeakPoint->HasValidWeakPoint());
	TestFalse(TEXT("Missing head never gains a multiplier"),R->ResolveContact(F.Source,F.Enemy,F.Contact(),F.Attack).bWeakPointHit);
	F.Enemy->WeakPoint->HeadBoneName = NAME_None;
	F.Enemy->Vitals->DamageProtectionSeconds = 10;
	TestTrue(TEXT("Armor/protection rejects head contact"),!R->ResolveContact(F.Source,F.Enemy,F.Contact(),F.Attack).bWeakPointHit);
	F.Enemy->Vitals->DamageProtectionSeconds = 0;
	F.Enemy->SetLabPaused(true);
	TestFalse(TEXT("Locally paused target does not award head feedback"),R->ResolveContact(F.Source,F.Enemy,F.Contact(),F.Attack).bWeakPointHit);
	F.Enemy->SetLabPaused(false); F.Enemy->GetEnemyBrain()->SetComponentTickEnabled(false);
	F.Enemy->Vitals->Health = 0;
	TestFalse(TEXT("Dead target emits no weak-point result"),R->ResolveContact(F.Source,F.Enemy,F.Contact(),F.Attack).bWeakPointHit);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLWeakPointBladeAndWallTest,
	"Nilin.Combat.WeakPoint.RealBladeSamplesAndWorldObstruction", NLWeakPointTests::Flags)
bool FNLWeakPointBladeAndWallTest::RunTest(const FString& Parameters)
{
	NLWeakPointTests::FWorld F; if (!TestTrue(TEXT("Real mesh fixture ready"), F.Ready())) return false;
	USceneComponent* Weapon = NewObject<USceneComponent>(F.Source);
	F.Source->AddInstanceComponent(Weapon); Weapon->SetupAttachment(F.Source->GetRootComponent()); Weapon->RegisterComponent();
	UNLBladeComponent* Blade = NewObject<UNLBladeComponent>(F.Source);
	F.Source->AddInstanceComponent(Blade); Blade->AttackDefinition=F.Attack; Blade->RegisterComponent();
	Blade->ConfigureBlade(Weapon,F.Source->GetRootComponent()); Blade->SetComponentTickEnabled(false);
	Blade->BladeRootLocal=FVector::ZeroVector; Blade->BladeMidLocal=FVector(0,35,0); Blade->BladeTipLocal=FVector(0,70,0);
	Weapon->SetWorldLocation(F.Head()+FVector(-8,-65,0));
	Blade->BeginAttackWindow(); F.Step(.02f); Blade->TickComponent(.02f,LEVELTICK_All,&Blade->PrimaryComponentTick);
	Weapon->SetWorldLocation(F.Head()+FVector(8,-65,0));
	F.Step(.02f); Blade->TickComponent(.02f,LEVELTICK_All,&Blade->PrimaryComponentTick);
	TestEqual(TEXT("Earlier capsule-only blade sample cannot swallow simultaneous tip/head hit"),100-F.Enemy->Vitals->GetHealth(),15.0f);
	F.Step(.02f); Blade->TickComponent(.02f,LEVELTICK_All,&Blade->PrimaryComponentTick);
	TestEqual(TEXT("Same blade attack cannot award another head hit"),100-F.Enemy->Vitals->GetHealth(),15.0f);
	Blade->EndAttackWindow();
	// This wall sits inside the broad capsule, between its front skin and skull.
	// The pre-existing broad contact may still deal ordinary damage, never head reward.
	AActor* Wall = F.WallAt(F.Head()+FVector(-15,0,0));
	TestTrue(TEXT("Wall fixture exists"),Wall!=nullptr);
	TestEqual(TEXT("A head behind a thin wall cannot gain bonus through early body skin"),F.FireDamage(F.Head()-FVector(100,0,0)),10.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLWeakPointSlowNativeBladeTest,
	"Nilin.Combat.WeakPoint.NativeBladeSmallFrameRegionClassification", NLWeakPointTests::Flags)
bool FNLWeakPointSlowNativeBladeTest::RunTest(const FString& Parameters)
{
	NLWeakPointTests::FWorld F; if (!TestTrue(TEXT("Real mesh fixture ready"), F.Ready())) return false;
	USceneComponent* Weapon = NewObject<USceneComponent>(F.Source);
	F.Source->AddInstanceComponent(Weapon); Weapon->SetupAttachment(F.Source->GetRootComponent()); Weapon->RegisterComponent();
	UNLBladeComponent* Blade = NewObject<UNLBladeComponent>(F.Source);
	F.Source->AddInstanceComponent(Blade); Blade->AttackDefinition=F.Attack; Blade->RegisterComponent();
	Blade->ConfigureBlade(Weapon,F.Source->GetRootComponent()); Blade->SetComponentTickEnabled(false);
	// Preserve the production sword's +Z root/middle/tip samples. Lay it horizontally
	// and translate by 3cm per 10ms; the capsule is touched several frames before the skull.
	const auto Slash = [&](float OriginX)
	{
		F.Enemy->Vitals->ResetVitals(); Blade->ResetBladeHistory();
		const FVector Origin = F.Head()+FVector(OriginX,-50,0);
		Weapon->SetWorldLocationAndRotation(Origin,FRotationMatrix::MakeFromZ(FVector::ForwardVector).Rotator());
		Blade->BeginAttackWindow();
		F.Step(); Blade->TickComponent(.01f,LEVELTICK_All,&Blade->PrimaryComponentTick);
		for(int32 Index=1;Index<=36;++Index)
		{
			Weapon->SetWorldLocation(Origin+FVector(0,Index*3.0,0));
			F.Step(); Blade->TickComponent(.01f,LEVELTICK_All,&Blade->PrimaryComponentTick);
		}
		Blade->EndAttackWindow();
		return 100-F.Enemy->Vitals->GetHealth();
	};
	TestEqual(TEXT("Fine-step real sword through skull still receives exactly one 1.5x hit"),Slash(-80),15.0f);
	TestEqual(TEXT("Fine-step outer capsule graze with a short tip remains body damage"),Slash(-96),10.0f);
	return true;
}

#endif
