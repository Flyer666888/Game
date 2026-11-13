#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Components/SceneComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/GameInstance.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/WorldSettings.h"
#include "Misc/AutomationTest.h"
#include "Objective/NLRitualObjective.h"
#include "Progression/NLRunStateSubsystem.h"
#include "Progression/NLUpgradeDefinition.h"

namespace NLProgressionDamageTests
{
    constexpr EAutomationTestFlags Flags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    struct FBody
    {
        AActor* Actor = nullptr;
        UNLCombatIdentityComponent* Identity = nullptr;
        UNLCombatVitalsComponent* Vitals = nullptr;
        bool IsReady() const { return Actor && Identity && Vitals; }
    };

    /** Real resolver and game-instance progression; no master awards, saves or project assets are modified. */
    struct FWorld
    {
        UWorld* World = nullptr;
        UGameInstance* Instance = nullptr;
        UNLRunStateSubsystem* Run = nullptr;
        UNLCombatResolverSubsystem* Resolver = nullptr;
        UNLUpgradeDefinition* Upgrade = nullptr;
        UNLAttackDefinition* Attack = nullptr;
        ANLRitualObjective* Ritual = nullptr;
        FBody Player, Enemy;
        const uint64 SavedFrameCounter = GFrameCounter;

        FWorld()
        {
            if (!GEngine) return;
            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false).EnableTraceCollision(true).CreateNavigation(false).CreateAISystem(false);
            const FName Name(*FString::Printf(TEXT("NilinProgressionDamage_%s"), *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
            World = UWorld::CreateWorld(EWorldType::Game, false, Name, nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (!World) return;
            Instance = NewObject<UGameInstance>(GEngine);
            World->SetGameInstance(Instance);
            FWorldContext& Context = GEngine->CreateNewWorldContext(EWorldType::Game);
            Context.SetCurrentWorld(World);
            Context.OwningGameInstance = Instance;
            Instance->Init();
            Run = Instance->GetSubsystem<UNLRunStateSubsystem>();
            if (Run) Run->BeginRun(FGuid::NewGuid());
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();
            Resolver = World->GetSubsystem<UNLCombatResolverSubsystem>();
            Upgrade = NewObject<UNLUpgradeDefinition>(Instance);
            Attack = NewObject<UNLAttackDefinition>(World);
            Attack->StableId = TEXT("Attack.Test.ProgressionDamage");
            Attack->Damage = 10.0f;
            Attack->bCanBeBlocked = false;
            Player = AddBody(ENLCombatFaction::Player, true);
            Enemy = AddBody(ENLCombatFaction::Enemy, false);
            Ritual = World->SpawnActor<ANLRitualObjective>();
            if (Ritual)
            {
                Ritual->InitializeObjective(TEXT("Objective.Test.ProgressionDamage"), 100.0f, 240.0f);
                Ritual->AllowedAttackDefinitionIds.Add(Attack->StableId);
            }
        }
        ~FWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                if (GEngine) GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
            }
            if (Instance) Instance->Shutdown();
            GFrameCounter = SavedFrameCounter;
        }
        bool IsReady() const
        {
            return World && Instance && Run && Resolver && Upgrade && Attack && Ritual
                && Ritual->HasActorBegunPlay() && Player.IsReady() && Enemy.IsReady();
        }
        FBody AddBody(ENLCombatFaction Faction, bool bPawn)
        {
            FBody Body;
            Body.Actor = bPawn ? World->SpawnActor<APawn>() : World->SpawnActor<AActor>();
            if (!Body.Actor) return Body;
            USceneComponent* Root = NewObject<USceneComponent>(Body.Actor);
            Body.Actor->SetRootComponent(Root);
            Body.Actor->AddInstanceComponent(Root);
            Root->RegisterComponent();
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
            return Body;
        }
        FNLCombatContact Contact(const FBody& Source, AActor* Target) const
        {
            FNLCombatContact Contact;
            Contact.AttackInstanceId = FGuid::NewGuid();
            Contact.SourceRuntimeId = Source.Identity->EnsureRuntimeId();
            Contact.TargetRuntimeId = Target->FindComponentByClass<UNLCombatIdentityComponent>()->EnsureRuntimeId();
            Contact.ProjectileGeneration = INDEX_NONE;
            Contact.ContactTimeSeconds = World->GetTimeSeconds();
            Contact.HitPosition = Target->GetActorLocation();
            Contact.AttackDefinitionId = Attack->StableId;
            return Contact;
        }
        FNLCombatResult Hit(const FBody& Source, AActor* Target)
        {
            return Resolver->ResolveContact(Source.Actor, Target, Contact(Source, Target), Attack);
        }
    };
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLProgressionDamageResolverTest,
    "Nilin.Combat.Progression.CentralDamageMultiplierFactionDedupAndRollback", NLProgressionDamageTests::Flags)
bool FNLProgressionDamageResolverTest::RunTest(const FString& Parameters)
{
    using namespace NLProgressionDamageTests;
    FWorld Fixture;
    if (!TestTrue(TEXT("Real world, GameInstance, run state and resolver initialize"), Fixture.IsReady())) return false;
    TestEqual(TEXT("An unconfigured scene retains ordinary player damage"), Fixture.Hit(Fixture.Player, Fixture.Enemy.Actor).AppliedDamage, 10.0f);
    TestTrue(TEXT("First-level definition is configured on the actual GameInstance subsystem"), Fixture.Run->ConfigureUpgradeDefinition(Fixture.Upgrade));
    Fixture.Enemy.Vitals->ResetVitals();
    TestEqual(TEXT("Configured level one still deals the definition's ten damage"), Fixture.Hit(Fixture.Player, Fixture.Enemy.Actor).AppliedDamage, 10.0f);
    const FNLProgressionState Entrance = Fixture.Run->GetProgressionState();
    TestTrue(TEXT("Real unique reward grants the level-two upgrade"), Fixture.Run->AwardLingQi(TEXT("Test.UpgradeReward"), 40.0f));
    Fixture.Enemy.Vitals->ResetVitals();
    const FNLCombatContact UpgradedContact = Fixture.Contact(Fixture.Player, Fixture.Enemy.Actor);
    const FNLCombatResult Upgraded = Fixture.Resolver->ResolveContact(Fixture.Player.Actor, Fixture.Enemy.Actor, UpgradedContact, Fixture.Attack);
    TestTrue(TEXT("Upgraded contact is a real hit"), Upgraded.Outcome == ENLCombatOutcome::Hit);
    TestEqual(TEXT("Central resolver applies exactly one 1.25 multiplier"), Upgraded.AppliedDamage, 12.5f);
    TestEqual(TEXT("Enemy vitals lose the corresponding real health"), Fixture.Enemy.Vitals->GetHealth(), 87.5f);
    const FNLCombatResult Repeated = Fixture.Resolver->ResolveContact(Fixture.Player.Actor, Fixture.Enemy.Actor, UpgradedContact, Fixture.Attack);
    TestTrue(TEXT("Growth does not bypass per-attack contact deduplication"), Repeated.Outcome == ENLCombatOutcome::Ignored);
    TestEqual(TEXT("Repeated contact cannot apply upgraded damage twice"), Fixture.Enemy.Vitals->GetHealth(), 87.5f);
    TestEqual(TEXT("Runtime growth never mutates the shared attack definition"), Fixture.Attack->Damage, 10.0f);

    const FNLCombatResult EnemyHit = Fixture.Hit(Fixture.Enemy, Fixture.Player.Actor);
    TestEqual(TEXT("Player growth does not increase incoming enemy damage"), EnemyHit.AppliedDamage, 10.0f);
    TestEqual(TEXT("Player vitals reflect the original enemy damage"), Fixture.Player.Vitals->GetHealth(), 90.0f);
    const FNLCombatResult RitualHit = Fixture.Hit(Fixture.Enemy, Fixture.Ritual);
    TestTrue(TEXT("Whitelisted enemy contact still uses the actual ritual pipeline"), RitualHit.Outcome == ENLCombatOutcome::RitualDamaged);
    TestEqual(TEXT("Player growth does not increase damage to the rescue objective"), RitualHit.AppliedDamage, 10.0f);
    TestEqual(TEXT("Ritual integrity loses only the unmodified enemy damage"), Fixture.Ritual->GetIntegrity(), 90.0f);

    TestTrue(TEXT("Leaving the growth-enabled scene disables its definition"), Fixture.Run->ConfigureUpgradeDefinition(nullptr));
    Fixture.Enemy.Vitals->ResetVitals();
    TestEqual(TEXT("Saved level two alone cannot affect damage in an unconfigured scene"), Fixture.Hit(Fixture.Player, Fixture.Enemy.Actor).AppliedDamage, 10.0f);
    TestTrue(TEXT("Re-entering the growth-enabled scene restores its configured effect"), Fixture.Run->ConfigureUpgradeDefinition(Fixture.Upgrade));
    TestTrue(TEXT("A failed segment can restore its true level-one entrance"), Fixture.Run->RestoreProgressionState(Entrance));
    Fixture.Enemy.Vitals->ResetVitals();
    TestEqual(TEXT("The resolver reads the restored level instead of caching the old upgrade"), Fixture.Hit(Fixture.Player, Fixture.Enemy.Actor).AppliedDamage, 10.0f);
    TestEqual(TEXT("The shared attack definition is unchanged after every path"), Fixture.Attack->Damage, 10.0f);
    return true;
}

#endif
