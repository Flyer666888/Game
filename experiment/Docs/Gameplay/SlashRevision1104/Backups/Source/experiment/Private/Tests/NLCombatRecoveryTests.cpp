#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLBladeComponent.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatRecoveryComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Combat/NLGuardComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include <limits>

namespace NLCombatRecoveryTests
{
	constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;

	struct FBody
	{
		AActor* Actor = nullptr;
		UNLCombatIdentityComponent* Identity = nullptr;
		UNLCombatVitalsComponent* Vitals = nullptr;
		UNLGuardComponent* Guard = nullptr;
		UNLCombatRecoveryComponent* Recovery = nullptr;
		UBoxComponent* Barrier = nullptr;
		bool IsReady() const { return Actor && Identity && Vitals && Guard && Recovery && Barrier; }
	};

	/** A real resolver + directional guard in an isolated world, without a headset or game save. */
	class FScopedRecoveryWorld
	{
	public:
		FScopedRecoveryWorld() : SavedFrameCounter(GFrameCounter)
		{
			if (!GEngine) return;
			const UWorld::InitializationValues Values = UWorld::InitializationValues()
				.AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
				.ShouldSimulatePhysics(false).EnableTraceCollision(true)
				.CreateNavigation(false).CreateAISystem(false);
			const FName Name(*FString::Printf(TEXT("NilinRecoveryTest_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
			World = UWorld::CreateWorld(EWorldType::Game, false, Name, nullptr, true, ERHIFeatureLevel::Num, &Values);
			if (!World) return;
			GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
			World->InitializeActorsForPlay(FURL());
			World->BeginPlay();
			if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();
			Resolver = World->GetSubsystem<UNLCombatResolverSubsystem>();
			Definition = NewObject<UNLAttackDefinition>(World);
			Definition->StableId = TEXT("Test.Recovery.ReflectableBolt");
			Definition->Damage = 20.0f;
			Definition->bCanBeBlocked = true;
			Definition->bCanBeParried = true;
			Definition->bCanBeReflected = true;
			Enemy = AddBody(ENLCombatFaction::Enemy, FVector(1000.0, 0.0, 100.0));
			Player = AddBody(ENLCombatFaction::Player, FVector(0.0, 0.0, 100.0));
		}

		~FScopedRecoveryWorld()
		{
			if (World)
			{
				World->EndPlay(EEndPlayReason::Quit);
				if (GEngine) GEngine->DestroyWorldContext(World);
				World->DestroyWorld(false);
			}
			GFrameCounter = SavedFrameCounter;
		}

		bool IsReady() const
		{
			return World && Resolver && Definition && Player.IsReady() && Enemy.IsReady()
				&& Player.Recovery->HasBegunPlay();
		}

		FBody AddBody(ENLCombatFaction Faction, const FVector& Position)
		{
			FBody Body;
			FActorSpawnParameters Spawn;
			Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
			Body.Actor = World->SpawnActor<AActor>(Position, FRotator::ZeroRotator, Spawn);
			if (!Body.Actor) return Body;
			USceneComponent* Root = NewObject<USceneComponent>(Body.Actor);
			Body.Actor->SetRootComponent(Root);
			Body.Actor->AddInstanceComponent(Root);
			Root->RegisterComponent();
			Root->SetWorldLocation(Position);
			Body.Identity = NewObject<UNLCombatIdentityComponent>(Body.Actor);
			Body.Identity->Faction = Faction;
			Body.Actor->AddInstanceComponent(Body.Identity);
			Body.Identity->RegisterComponent();
			Body.Identity->EnsureRuntimeId();
			Body.Vitals = NewObject<UNLCombatVitalsComponent>(Body.Actor);
			Body.Vitals->DamageProtectionSeconds = 0.0f;
			Body.Actor->AddInstanceComponent(Body.Vitals);
			Body.Vitals->RegisterComponent();
			Body.Vitals->ResetVitals();
			Body.Barrier = NewObject<UBoxComponent>(Body.Actor);
			Body.Barrier->SetupAttachment(Root);
			Body.Barrier->InitBoxExtent(FVector(10.0, 60.0, 60.0));
			Body.Actor->AddInstanceComponent(Body.Barrier);
			Body.Barrier->RegisterComponent();
			Body.Barrier->SetRelativeLocation(FVector(40.0, 0.0, 0.0));
			Body.Guard = NewObject<UNLGuardComponent>(Body.Actor);
			Body.Guard->MaintenanceCostPerSecond = 0.0f;
			Body.Guard->MinimumPerfectRaiseInterval = 0.0f;
			Body.Guard->ReleaseRearmSeconds = 0.0f;
			Body.Actor->AddInstanceComponent(Body.Guard);
			Body.Guard->RegisterComponent();
			Body.Guard->ConfigureGuard(Body.Barrier, nullptr);
			Body.Recovery = NewObject<UNLCombatRecoveryComponent>(Body.Actor);
			Body.Actor->AddInstanceComponent(Body.Recovery);
			Body.Recovery->RegisterComponent();
			return Body;
		}

		FNLCombatContact MakeContact(const FBody& Target) const
		{
			FNLCombatContact Contact;
			Contact.AttackInstanceId = FGuid::NewGuid();
			Contact.SourceRuntimeId = Enemy.Identity->EnsureRuntimeId();
			Contact.TargetRuntimeId = Target.Identity->EnsureRuntimeId();
			Contact.ProjectileGeneration = 0;
			Contact.ContactTimeSeconds = World->GetTimeSeconds();
			Contact.HitPosition = Target.Barrier->GetComponentLocation();
			Contact.IncomingVelocity = FVector(-1000.0, 0.0, 0.0);
			Contact.AttackDefinitionId = Definition->StableId;
			return Contact;
		}

		FNLCombatResult Parry(const FNLCombatContact& Contact, bool bAllowPerfect = true)
		{
			Player.Guard->SetGuardHeld(false);
			Player.Guard->SetGuardHeld(true);
			return Resolver->ResolveGuardContact(Enemy.Actor, Player.Actor, Contact, Definition, Player.Guard, bAllowPerfect);
		}
		FNLCombatResult Parry() { return Parry(MakeContact(Player)); }

		UWorld* World = nullptr;
		UNLCombatResolverSubsystem* Resolver = nullptr;
		UNLAttackDefinition* Definition = nullptr;
		FBody Enemy;
		FBody Player;
	private:
		uint64 SavedFrameCounter;
	};
}

using namespace NLCombatRecoveryTests;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLCombatRecoveryResolverTest,
	"Nilin.Combat.Recovery.ResolverValidatedPerfectParries", NLCombatRecoveryTests::TestFlags)

bool FNLCombatRecoveryResolverTest::RunTest(const FString& Parameters)
{
	FScopedRecoveryWorld Fixture;
	if (!TestTrue(TEXT("Real resolver, guard and recovery components begin play"), Fixture.IsReady())) return false;
	UNLCombatRecoveryComponent* Recovery = Fixture.Player.Recovery;
	Fixture.Player.Vitals->ApplyCombatDamage(30.0f);
	const FNLCombatContact FirstContact = Fixture.MakeContact(Fixture.Player);
	const FNLCombatResult First = Fixture.Parry(FirstContact);
	TestTrue(TEXT("Directional reflectable projectile resolves a genuine perfect parry"), First.Outcome == ENLCombatOutcome::PerfectParry);
	TestEqual(TEXT("First validated result earns one charge"), Recovery->GetRecoveryCharges(), 1);
	const FNLCombatResult Duplicate = Fixture.Parry(FirstContact);
	TestTrue(TEXT("Resolver rejects repeated attack/target"), Duplicate.Outcome == ENLCombatOutcome::Ignored);
	Fixture.Resolver->OnCombatResult.Broadcast(First);
	FNLCombatResult ReissuedResult = First;
	ReissuedResult.ResultId = FGuid::NewGuid();
	Fixture.Resolver->OnCombatResult.Broadcast(ReissuedResult);
	TestEqual(TEXT("Duplicate notifications and a new result ID for one attack cannot multiply charges"), Recovery->GetRecoveryCharges(), 1);

	const FNLCombatResult Ordinary = Fixture.Parry(Fixture.MakeContact(Fixture.Player), false);
	TestTrue(TEXT("Ordinary block is resolved by the same guard path"), Ordinary.Outcome == ENLCombatOutcome::Blocked);
	TestEqual(TEXT("Ordinary block earns no charge"), Recovery->GetRecoveryCharges(), 1);
	FNLCombatContact Invalid = Fixture.MakeContact(Fixture.Player);
	Invalid.SourceRuntimeId = FGuid::NewGuid();
	TestTrue(TEXT("Mismatched source identity is rejected"), Fixture.Parry(Invalid).Outcome == ENLCombatOutcome::Ignored);
	Fixture.Enemy.Identity->Faction = ENLCombatFaction::Player;
	TestTrue(TEXT("Friendly-fire defense is rejected before rewarding recovery"), Fixture.Parry().Outcome == ENLCombatOutcome::Ignored);
	Fixture.Enemy.Identity->Faction = ENLCombatFaction::Enemy;
	TestEqual(TEXT("Invalid/friendly contacts earn no charge"), Recovery->GetRecoveryCharges(), 1);

	const FBody OtherPlayer = Fixture.AddBody(ENLCombatFaction::Player, FVector(0.0, 500.0, 100.0));
	OtherPlayer.Vitals->ApplyCombatDamage(30.0f);
	OtherPlayer.Guard->SetGuardHeld(true);
	const FNLCombatResult OtherResult = Fixture.Resolver->ResolveGuardContact(Fixture.Enemy.Actor, OtherPlayer.Actor,
		Fixture.MakeContact(OtherPlayer), Fixture.Definition, OtherPlayer.Guard, true);
	TestTrue(TEXT("Another actor has a valid perfect parry"), OtherResult.Outcome == ENLCombatOutcome::PerfectParry);
	TestEqual(TEXT("Another target's result does not reward this player"), Recovery->GetRecoveryCharges(), 1);
	TestEqual(TEXT("The actual other target receives its own charge"), OtherPlayer.Recovery->GetRecoveryCharges(), 1);
	TestTrue(TEXT("Second distinct perfect parry succeeds"), Fixture.Parry().Outcome == ENLCombatOutcome::PerfectParry);
	TestEqual(TEXT("Two charges do not heal early"), Fixture.Player.Vitals->GetHealth(), 70.0f);
	TestTrue(TEXT("Third distinct perfect parry succeeds"), Fixture.Parry().Outcome == ENLCombatOutcome::PerfectParry);
	TestEqual(TEXT("Three perfect parries automatically restore ten health"), Fixture.Player.Vitals->GetHealth(), 80.0f);
	TestEqual(TEXT("The heal consumes all charges"), Recovery->GetRecoveryCharges(), 0);
	TestEqual(TEXT("HUD feedback exposes actual recovered health"), Recovery->GetLastRecoveredHealth(), 10.0f);
	TestTrue(TEXT("HUD feedback exposes game-time heal timestamp"), Recovery->GetLastRecoveryTimeSeconds() >= 0.0);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLCombatRecoveryMeleeRulesTest,
	"Nilin.Combat.Recovery.MeleeParryAndProjectileRules", NLCombatRecoveryTests::TestFlags)

bool FNLCombatRecoveryMeleeRulesTest::RunTest(const FString& Parameters)
{
	FScopedRecoveryWorld Fixture;
	if (!TestTrue(TEXT("Real resolver and directional guard begin play"), Fixture.IsReady())) return false;
	Fixture.Player.Vitals->ApplyCombatDamage(30.0f);
	Fixture.Definition->bCanBeReflected = false;
	FNLCombatContact Melee = Fixture.MakeContact(Fixture.Player);
	Melee.ProjectileGeneration = INDEX_NONE;
	// The existing blade caller passes false: it does not reflect melee weapons.
	// Lateral swing velocity must still use the attacker's position for facing.
	Melee.IncomingVelocity = FVector(0.0, 1200.0, 0.0);
	const FNLCombatResult Perfect = Fixture.Parry(Melee, false);
	TestTrue(TEXT("Timed melee guard parries without projectile reflection permission"), Perfect.Outcome == ENLCombatOutcome::PerfectParry);
	TestTrue(TEXT("Melee parry does not assign a projectile faction"), Perfect.NewProjectileFaction == ENLCombatFaction::Neutral);
	TestEqual(TEXT("Melee parry contributes one recovery charge"), Fixture.Player.Recovery->GetRecoveryCharges(), 1);
	TestEqual(TEXT("Melee parry consumes the perfect-window guard cost"), Perfect.GuardSpent, Fixture.Player.Guard->PerfectGuardCost);
	TestTrue(TEXT("Same melee attack cannot be rewarded again"), Fixture.Parry(Melee, false).Outcome == ENLCombatOutcome::Ignored);

	Fixture.Definition->bCanBeParried = false;
	Melee.AttackInstanceId = FGuid::NewGuid();
	const FNLCombatResult Ordinary = Fixture.Parry(Melee, false);
	TestTrue(TEXT("Blockable but unparryable melee stays an ordinary block"), Ordinary.Outcome == ENLCombatOutcome::Blocked);
	TestEqual(TEXT("Ordinary melee block pays the existing melee cost"), Ordinary.GuardSpent, Fixture.Player.Guard->MeleeBlockGuardCost);
	TestEqual(TEXT("Ordinary melee block earns no recovery charge"), Fixture.Player.Recovery->GetRecoveryCharges(), 1);

	Fixture.Definition->bCanBeParried = true;
	Fixture.Definition->bCanBeBlocked = false;
	Melee.AttackInstanceId = FGuid::NewGuid();
	TestTrue(TEXT("Unblockable melee is never converted into a perfect parry"), Fixture.Parry(Melee, false).Outcome == ENLCombatOutcome::Ignored);
	Fixture.Definition->bCanBeBlocked = true;
	Fixture.Enemy.Actor->SetActorLocation(FVector(-1000.0, 0.0, 100.0));
	Melee.AttackInstanceId = FGuid::NewGuid();
	TestTrue(TEXT("Melee from behind is rejected by the directional guard"), Fixture.Parry(Melee, false).Outcome == ENLCombatOutcome::Ignored);
	Fixture.Enemy.Actor->SetActorLocation(FVector(1000.0, 0.0, 100.0));

	TestTrue(TEXT("Nonreflectable projectile stays an ordinary block in the timing window"),
		Fixture.Parry(Fixture.MakeContact(Fixture.Player), true).Outcome == ENLCombatOutcome::Blocked);
	Fixture.Definition->bCanBeReflected = true;
	TestTrue(TEXT("Reflection-disabled caller cannot perfect-parry a projectile"),
		Fixture.Parry(Fixture.MakeContact(Fixture.Player), false).Outcome == ENLCombatOutcome::Blocked);
	const FNLCombatResult Reflected = Fixture.Parry(Fixture.MakeContact(Fixture.Player), true);
	TestTrue(TEXT("Reflectable projectile keeps the existing perfect reflection behavior"), Reflected.Outcome == ENLCombatOutcome::PerfectParry);
	TestTrue(TEXT("Reflected projectile changes to the defending player's faction"), Reflected.NewProjectileFaction == ENLCombatFaction::Player);
	TestEqual(TEXT("Only genuine melee and projectile parries contributed charges"), Fixture.Player.Recovery->GetRecoveryCharges(), 2);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLCombatRecoveryMeleeBladeSweepTest,
	"Nilin.Combat.Recovery.ThreeActualMeleeSweepsHeal", NLCombatRecoveryTests::TestFlags)

bool FNLCombatRecoveryMeleeBladeSweepTest::RunTest(const FString& Parameters)
{
	FScopedRecoveryWorld Fixture;
	if (!TestTrue(TEXT("Physics world, directional guard and recovery begin play"), Fixture.IsReady())) return false;
	Fixture.Player.Vitals->ApplyCombatDamage(30.0f);
	Fixture.Definition->bCanBeReflected = false;
	USceneComponent* Weapon = NewObject<USceneComponent>(Fixture.Enemy.Actor);
	Weapon->SetupAttachment(Fixture.Enemy.Actor->GetRootComponent());
	Fixture.Enemy.Actor->AddInstanceComponent(Weapon);
	Weapon->RegisterComponent();
	UNLBladeComponent* Blade = NewObject<UNLBladeComponent>(Fixture.Enemy.Actor);
	Fixture.Enemy.Actor->AddInstanceComponent(Blade);
	Blade->AttackDefinition = Fixture.Definition;
	Blade->BladeRootLocal = FVector::ZeroVector;
	Blade->BladeMidLocal = FVector(0.0, 0.0, 10.0);
	Blade->BladeTipLocal = FVector(0.0, 0.0, 20.0);
	Blade->RegisterComponent();
	Blade->ConfigureBlade(Weapon, Fixture.Enemy.Actor->GetRootComponent());
	Blade->SetComponentTickEnabled(false);
	const auto Sample = [&Fixture, Blade]()
	{
		Fixture.World->Tick(LEVELTICK_All, 0.02f);
		Blade->TickComponent(0.02f, LEVELTICK_All, &Blade->PrimaryComponentTick);
		++GFrameCounter;
	};
	for (int32 Swing = 0; Swing < 3; ++Swing)
	{
		Fixture.Player.Guard->SetGuardHeld(false);
		Fixture.Player.Guard->SetGuardHeld(true);
		Weapon->SetWorldLocation(FVector(40.0, 100.0, 90.0));
		TestTrue(TEXT("Actual AI-owned melee window starts"), Blade->BeginAttackWindow());
		Sample(); // The first animation sample only establishes the baseline.
		Weapon->SetWorldLocation(FVector(40.0, 40.0, 90.0));
		Sample(); // A lateral blade sweep contacts the finite guard collision.
		TestEqual(TEXT("Only one recovery charge is earned per actual sword swing"),
			Fixture.Player.Recovery->GetRecoveryCharges(), Swing < 2 ? Swing + 1 : 0);
		Sample(); // Many blade samples and an overlapping frame must not multiply rewards.
		TestEqual(TEXT("A continued sword overlap cannot reward multiple parries"),
			Fixture.Player.Recovery->GetRecoveryCharges(), Swing < 2 ? Swing + 1 : 0);
		Blade->EndAttackWindow();
	}
	TestEqual(TEXT("Three physical melee sweeps restore exactly ten HP"), Fixture.Player.Vitals->GetHealth(), 80.0f);
	TestEqual(TEXT("Physical melee parries expose real heal feedback"), Fixture.Player.Recovery->GetLastRecoveredHealth(), 10.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLCombatRecoveryFullHealthDeathTest,
	"Nilin.Combat.Recovery.FullHealthDeathAndRetry", NLCombatRecoveryTests::TestFlags)

bool FNLCombatRecoveryFullHealthDeathTest::RunTest(const FString& Parameters)
{
	FScopedRecoveryWorld Fixture;
	if (!TestTrue(TEXT("Fixture begins play"), Fixture.IsReady())) return false;
	UNLCombatRecoveryComponent* Recovery = Fixture.Player.Recovery;
	const FNLCombatResult FullHealthResult = Fixture.Parry();
	Fixture.Parry();
	TestEqual(TEXT("Full health never banks recovery charges"), Recovery->GetRecoveryCharges(), 0);
	Fixture.Player.Vitals->ApplyCombatDamage(20.0f);
	Fixture.Resolver->OnCombatResult.Broadcast(FullHealthResult);
	TestEqual(TEXT("A full-health result cannot be replayed after damage"), Recovery->GetRecoveryCharges(), 0);
	Fixture.Parry();
	TestEqual(TEXT("A fresh injured parry starts a new charge"), Recovery->GetRecoveryCharges(), 1);
	Fixture.Player.Vitals->RestoreHealth(20.0f);
	TestEqual(TEXT("External healing to full immediately clears stored progress"), Recovery->GetRecoveryCharges(), 0);
	Fixture.Player.Vitals->ApplyCombatDamage(20.0f);
	Fixture.Parry();
	Fixture.Parry();
	TestEqual(TEXT("Injured player can accumulate two fresh charges"), Recovery->GetRecoveryCharges(), 2);
	Fixture.Player.Vitals->ApplyCombatDamage(100.0f);
	TestEqual(TEXT("Death immediately clears charges"), Recovery->GetRecoveryCharges(), 0);
	TestEqual(TEXT("Restoring health cannot revive a dead actor"), Fixture.Player.Vitals->RestoreHealth(100.0f), 0.0f);
	TestTrue(TEXT("Dead actor cannot perfect parry"), Fixture.Parry().Outcome == ENLCombatOutcome::Ignored);
	TestEqual(TEXT("Death creates no healing"), Fixture.Player.Vitals->GetHealth(), 0.0f);
	Fixture.Player.Vitals->ResetVitals();
	Recovery->ResetRecovery();
	TestEqual(TEXT("Retry clears prior heal feedback"), Recovery->GetLastRecoveredHealth(), 0.0f);
	TestEqual(TEXT("Retry clears prior timestamp"), Recovery->GetLastRecoveryTimeSeconds(), -1.0);
	Fixture.Player.Vitals->ApplyCombatDamage(20.0f);
	Fixture.Parry();
	TestEqual(TEXT("Retry starts a clean recovery cycle"), Recovery->GetRecoveryCharges(), 1);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLCombatRecoveryPauseTest,
	"Nilin.Combat.Recovery.GlobalAndLocalPause", NLCombatRecoveryTests::TestFlags)

bool FNLCombatRecoveryPauseTest::RunTest(const FString& Parameters)
{
	FScopedRecoveryWorld Fixture;
	if (!TestTrue(TEXT("Fixture begins play"), Fixture.IsReady())) return false;
	Fixture.Player.Vitals->ApplyCombatDamage(30.0f);
	Fixture.Parry();
	FActorSpawnParameters Spawn;
	Spawn.bDeferConstruction = true;
	APlayerState* Pauser = Fixture.World->SpawnActor<APlayerState>(Spawn);
	if (!TestNotNull(TEXT("Real world pauser initializes"), Pauser)) return false;
	Fixture.World->GetWorldSettings()->SetPauserPlayerState(Pauser);
	TestTrue(TEXT("World reports a genuine pause"), Fixture.World->IsPaused());
	TestEqual(TEXT("Paused health restoration is rejected"), Fixture.Player.Vitals->RestoreHealth(10.0f), 0.0f);
	TestTrue(TEXT("Paused resolver rejects defense"), Fixture.Parry().Outcome == ENLCombatOutcome::Ignored);
	TestEqual(TEXT("Pause cannot accrue a charge"), Fixture.Player.Recovery->GetRecoveryCharges(), 1);
	Fixture.World->GetWorldSettings()->SetPauserPlayerState(nullptr);
	Fixture.Player.Recovery->SetCombatPaused(true);
	const FNLCombatResult DuringLocalPause = Fixture.Parry();
	TestTrue(TEXT("Resolver can publish while only the reward consumer is locally paused"), DuringLocalPause.Outcome == ENLCombatOutcome::PerfectParry);
	TestEqual(TEXT("Local pause rejects accrual"), Fixture.Player.Recovery->GetRecoveryCharges(), 1);
	Fixture.Player.Recovery->SetCombatPaused(false);
	Fixture.Resolver->OnCombatResult.Broadcast(DuringLocalPause);
	TestEqual(TEXT("A locally paused result cannot later be replayed for a charge"), Fixture.Player.Recovery->GetRecoveryCharges(), 1);
	Fixture.Parry();
	Fixture.Parry();
	TestEqual(TEXT("New valid parries continue the pre-pause cycle"), Fixture.Player.Vitals->GetHealth(), 80.0f);
	return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLCombatRestoreHealthSafetyTest,
	"Nilin.Combat.Recovery.RestoreHealthSafety", NLCombatRecoveryTests::TestFlags)

bool FNLCombatRestoreHealthSafetyTest::RunTest(const FString& Parameters)
{
	FScopedRecoveryWorld Fixture;
	if (!TestTrue(TEXT("Fixture begins play"), Fixture.IsReady())) return false;
	UNLCombatVitalsComponent* Vitals = Fixture.Player.Vitals;
	Vitals->ApplyCombatDamage(5.0f);
	TestEqual(TEXT("NaN restoration is rejected"), Vitals->RestoreHealth(std::numeric_limits<float>::quiet_NaN()), 0.0f);
	TestEqual(TEXT("Infinite restoration is rejected"), Vitals->RestoreHealth(std::numeric_limits<float>::infinity()), 0.0f);
	TestEqual(TEXT("Negative restoration is rejected"), Vitals->RestoreHealth(-10.0f), 0.0f);
	TestEqual(TEXT("Invalid healing leaves health unchanged"), Vitals->GetHealth(), 95.0f);
	TestEqual(TEXT("Heal returns the actual missing health"), Vitals->RestoreHealth(10.0f), 5.0f);
	TestEqual(TEXT("Healing clamps at maximum health"), Vitals->GetHealth(), 100.0f);
	TestEqual(TEXT("Full health restoration returns zero"), Vitals->RestoreHealth(10.0f), 0.0f);
	return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
