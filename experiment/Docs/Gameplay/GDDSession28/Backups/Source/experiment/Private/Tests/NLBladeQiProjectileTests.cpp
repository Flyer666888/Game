#if WITH_DEV_AUTOMATION_TESTS

#include "Combat/NLAttackDefinition.h"
#include "Combat/NLCombatIdentityComponent.h"
#include "Combat/NLCombatProjectile.h"
#include "Combat/NLCombatResolverSubsystem.h"
#include "Combat/NLCombatVitalsComponent.h"
#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/SphereComponent.h"
#include "CoreGlobals.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/WorldSettings.h"
#include "Materials/Material.h"
#include "Misc/AutomationTest.h"
#include "MotionControllerComponent.h"
#include "Player/NLDesktopPlayerCharacter.h"
#include "Player/NLVRPlayerCharacter.h"

namespace NLBladeQiProjectileTests
{
    constexpr EAutomationTestFlags TestFlags = EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter;
    constexpr float TestDamage = 15.0f;

    struct FBody
    {
        AActor* Actor = nullptr;
        UNLCombatIdentityComponent* Identity = nullptr;
        UNLCombatVitalsComponent* Vitals = nullptr;

        bool IsReady() const { return Actor && Identity && Vitals; }
    };

    /** An isolated query-enabled world: no pawn, XR runtime, game instance or save service. */
    class FScopedCombatWorld
    {
    public:
        FScopedCombatWorld()
            : SavedFrameCounter(GFrameCounter)
        {
            if (!GEngine) return;

            const UWorld::InitializationValues Values = UWorld::InitializationValues()
                .AllowAudioPlayback(false)
                .RequiresHitProxies(false)
                .CreatePhysicsScene(true)
                .ShouldSimulatePhysics(false)
                .EnableTraceCollision(true)
                .CreateNavigation(false)
                .CreateAISystem(false);
            const FName Name(*FString::Printf(TEXT("NilinBladeQiTest_%s"),
                *FGuid::NewGuid().ToString(EGuidFormats::Digits)));
            // CreateWorld calls InitializeNewWorld with Values exactly once.
            World = UWorld::CreateWorld(EWorldType::Game, false, Name, nullptr, true,
                ERHIFeatureLevel::Num, &Values);
            if (!World) return;

            GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
            bHasWorldContext = true;
            World->InitializeActorsForPlay(FURL());
            World->BeginPlay();
            // With no GameMode, BeginPlay starts world subsystems but does not
            // dispatch actors. Complete the standard WorldSettings notification.
            if (AWorldSettings* Settings = World->GetWorldSettings()) Settings->NotifyBeginPlay();

            Definition = NewObject<UNLAttackDefinition>(World);
            Definition->StableId = TEXT("Test.SwordQi");
            Definition->Damage = TestDamage;
            Definition->bCanBeBlocked = false;
            Definition->bCanBeParried = false;
            Definition->bCanBeReflected = false;
        }

        ~FScopedCombatWorld()
        {
            if (World)
            {
                World->EndPlay(EEndPlayReason::Quit);
                if (GEngine && bHasWorldContext) GEngine->DestroyWorldContext(World);
                World->DestroyWorld(false);
                World = nullptr;
            }
            // Manual test ticks must not advance the surrounding editor's frame identity.
            GFrameCounter = SavedFrameCounter;
        }

        FScopedCombatWorld(const FScopedCombatWorld&) = delete;
        FScopedCombatWorld& operator=(const FScopedCombatWorld&) = delete;

        bool IsReady() const
        {
            return World && World->GetPhysicsScene() && World->HasBegunPlay() && Definition
                && World->GetSubsystem<UNLCombatResolverSubsystem>();
        }

        FBody AddBody(ENLCombatFaction Faction, double X)
        {
            FBody Result;
            if (!World) return Result;

            FActorSpawnParameters Parameters;
            Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            Result.Actor = World->SpawnActor<AActor>(FVector(X, 0.0, 100.0), FRotator::ZeroRotator, Parameters);
            if (!Result.Actor) return Result;

            USphereComponent* Collision = NewObject<USphereComponent>(Result.Actor);
            Collision->InitSphereRadius(30.0f);
            Collision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
            Collision->SetCollisionObjectType(ECC_Pawn);
            Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
            Collision->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
            Collision->SetGenerateOverlapEvents(false);
            Collision->SetCanEverAffectNavigation(false);
            Result.Actor->SetRootComponent(Collision);
            Result.Actor->AddInstanceComponent(Collision);
            Collision->RegisterComponent();
            Collision->SetWorldLocation(FVector(X, 0.0, 100.0));

            Result.Identity = NewObject<UNLCombatIdentityComponent>(Result.Actor);
            Result.Identity->Faction = Faction;
            Result.Actor->AddInstanceComponent(Result.Identity);
            Result.Identity->RegisterComponent();
            Result.Identity->EnsureRuntimeId();

            Result.Vitals = NewObject<UNLCombatVitalsComponent>(Result.Actor);
            Result.Vitals->MaxHealth = 100.0f;
            // Duplicate contacts must be rejected by attack identity, not hidden by invulnerability.
            Result.Vitals->DamageProtectionSeconds = 0.0f;
            Result.Actor->AddInstanceComponent(Result.Vitals);
            Result.Vitals->RegisterComponent();
            Result.Vitals->ResetVitals();
            return Result;
        }

        AActor* AddWall(double X)
        {
            if (!World) return nullptr;
            FActorSpawnParameters Parameters;
            Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            AActor* Wall = World->SpawnActor<AActor>(FVector(X, 0.0, 100.0), FRotator::ZeroRotator, Parameters);
            if (!Wall) return nullptr;

            UBoxComponent* Collision = NewObject<UBoxComponent>(Wall);
            Collision->InitBoxExtent(FVector(20.0, 100.0, 100.0));
            Collision->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
            Collision->SetCollisionObjectType(ECC_WorldStatic);
            Collision->SetCollisionResponseToAllChannels(ECR_Ignore);
            Collision->SetCollisionResponseToChannel(ECC_GameTraceChannel3, ECR_Block);
            Collision->SetGenerateOverlapEvents(false);
            Collision->SetCanEverAffectNavigation(false);
            Wall->SetRootComponent(Collision);
            Wall->AddInstanceComponent(Collision);
            Collision->RegisterComponent();
            Collision->SetWorldLocation(FVector(X, 0.0, 100.0));
            return Wall;
        }

        ANLCombatProjectile* Fire(const FBody& Source, float Lifetime = 1.0f)
        {
            if (!IsReady() || !Source.IsReady()) return nullptr;
            FActorSpawnParameters Parameters;
            Parameters.Owner = Source.Actor;
            Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
            ANLCombatProjectile* Projectile = World->SpawnActor<ANLCombatProjectile>(
                FVector(0.0, 0.0, 100.0), FRotator::ZeroRotator, Parameters);
            if (!Projectile) return nullptr;
            // The regression only needs collision and damage, independent of project materials.
            Projectile->VisualMaterial = UMaterial::GetDefaultMaterial(MD_Surface);
            if (!Projectile->InitializeProjectile(Source.Actor, Definition, FVector::ForwardVector,
                24000.0f, 5.0f, Lifetime))
            {
                Projectile->Destroy();
                return nullptr;
            }
            return Projectile;
        }

        void Step(float DeltaSeconds)
        {
            World->Tick(LEVELTICK_All, DeltaSeconds);
            ++GFrameCounter;
        }

        UWorld* World = nullptr;
        UNLAttackDefinition* Definition = nullptr;

    private:
        uint64 SavedFrameCounter = 0;
        bool bHasWorldContext = false;
    };

    bool WasConsumed(const ANLCombatProjectile* Projectile)
    {
        return !IsValid(Projectile) || Projectile->IsActorBeingDestroyed();
    }
}

using namespace NLBladeQiProjectileTests;

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiProjectileSweptDamageTest,
    "Nilin.Combat.BladeQi.Projectile.HighSpeedSingleDamage", NLBladeQiProjectileTests::TestFlags)

bool FNLBladeQiProjectileSweptDamageTest::RunTest(const FString& Parameters)
{
    FScopedCombatWorld Fixture;
    if (!TestTrue(TEXT("A query-enabled game world begins play"), Fixture.IsReady())) return false;
    const FBody Source = Fixture.AddBody(ENLCombatFaction::Player, -100.0);
    const FBody Target = Fixture.AddBody(ENLCombatFaction::Enemy, 1000.0);
    const FBody Behind = Fixture.AddBody(ENLCombatFaction::Enemy, 1500.0);
    if (!TestTrue(TEXT("Minimal combat actors have identity and vitals"), Source.IsReady() && Target.IsReady() && Behind.IsReady())) return false;
    ANLCombatProjectile* Projectile = Fixture.Fire(Source);
    if (!TestNotNull(TEXT("A sword-qi projectile initializes"), Projectile)) return false;
    const FGuid AttackId = Projectile->GetAttackInstanceId();

    // One 0.1s frame travels 24m, completely crossing the 10m enemy's body.
    Fixture.Step(0.1f);
    TestEqual(TEXT("Swept projectile damages the 10m target once"), Target.Vitals->GetHealth(), 85.0f);
    TestEqual(TEXT("The enemy behind the first hit remains unharmed"), Behind.Vitals->GetHealth(), 100.0f);
    TestTrue(TEXT("The projectile is consumed on its first legal hit"), WasConsumed(Projectile));
    Fixture.Step(0.1f);
    TestEqual(TEXT("Later ticks cannot damage the first target again"), Target.Vitals->GetHealth(), 85.0f);
    TestEqual(TEXT("A consumed projectile never reaches the following target"), Behind.Vitals->GetHealth(), 100.0f);

    FNLCombatContact Duplicate;
    Duplicate.AttackInstanceId = AttackId;
    Duplicate.SourceRuntimeId = Source.Identity->EnsureRuntimeId();
    Duplicate.TargetRuntimeId = Target.Identity->EnsureRuntimeId();
    Duplicate.ProjectileGeneration = 0;
    Duplicate.AttackDefinitionId = Fixture.Definition->StableId;
    Duplicate.ContactTimeSeconds = Fixture.World->GetTimeSeconds();
    const FNLCombatResult Result = Fixture.World->GetSubsystem<UNLCombatResolverSubsystem>()->ResolveContact(
        Source.Actor, Target.Actor, Duplicate, Fixture.Definition);
    TestTrue(TEXT("Resolver rejects the same attack and generation a second time"),
        Result.FeedbackTag == TEXT("Combat.Ignored.DuplicateContact"));
    TestEqual(TEXT("Duplicate rejection does not depend on invulnerability"), Target.Vitals->GetHealth(), 85.0f);
    TestEqual(TEXT("The source receives no self damage"), Source.Vitals->GetHealth(), 100.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiProjectileWallTest,
    "Nilin.Combat.BladeQi.Projectile.WorldOcclusion", NLBladeQiProjectileTests::TestFlags)

bool FNLBladeQiProjectileWallTest::RunTest(const FString& Parameters)
{
    FScopedCombatWorld Fixture;
    if (!TestTrue(TEXT("World initializes"), Fixture.IsReady())) return false;
    const FBody Source = Fixture.AddBody(ENLCombatFaction::Player, -100.0);
    const FBody Target = Fixture.AddBody(ENLCombatFaction::Enemy, 1000.0);
    if (!TestTrue(TEXT("Combat bodies initialize"), Source.IsReady() && Target.IsReady())) return false;
    if (!TestNotNull(TEXT("A real world-static box blocks the path"), Fixture.AddWall(500.0))) return false;
    ANLCombatProjectile* Projectile = Fixture.Fire(Source);
    if (!TestNotNull(TEXT("Projectile initializes"), Projectile)) return false;

    Fixture.Step(0.1f);
    TestTrue(TEXT("The projectile is consumed by the nearer wall"), WasConsumed(Projectile));
    TestEqual(TEXT("An enemy behind a wall receives no damage"), Target.Vitals->GetHealth(), 100.0f);
    Fixture.Step(0.1f);
    TestEqual(TEXT("The wall continues to prevent delayed damage"), Target.Vitals->GetHealth(), 100.0f);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiProjectileFactionTest,
    "Nilin.Combat.BladeQi.Projectile.FriendlyAndNeutralFiltering", NLBladeQiProjectileTests::TestFlags)

bool FNLBladeQiProjectileFactionTest::RunTest(const FString& Parameters)
{
    FScopedCombatWorld Fixture;
    if (!TestTrue(TEXT("World initializes"), Fixture.IsReady())) return false;
    const FBody Source = Fixture.AddBody(ENLCombatFaction::Player, -100.0);
    const FBody Friendly = Fixture.AddBody(ENLCombatFaction::Player, 300.0);
    const FBody Neutral = Fixture.AddBody(ENLCombatFaction::Neutral, 600.0);
    const FBody Enemy = Fixture.AddBody(ENLCombatFaction::Enemy, 1000.0);
    if (!TestTrue(TEXT("All faction bodies initialize"), Source.IsReady() && Friendly.IsReady() && Neutral.IsReady() && Enemy.IsReady())) return false;
    ANLCombatProjectile* Projectile = Fixture.Fire(Source);
    if (!TestNotNull(TEXT("Projectile initializes"), Projectile)) return false;

    Fixture.Step(0.1f);
    TestEqual(TEXT("The player ally is not damaged"), Friendly.Vitals->GetHealth(), 100.0f);
    TestEqual(TEXT("The neutral body is not damaged"), Neutral.Vitals->GetHealth(), 100.0f);
    TestEqual(TEXT("The enemy behind both filtered blockers is hit"), Enemy.Vitals->GetHealth(), 85.0f);
    TestTrue(TEXT("The projectile is consumed by the legal enemy"), WasConsumed(Projectile));
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiProjectileLifetimeTest,
    "Nilin.Combat.BladeQi.Projectile.Lifetime", NLBladeQiProjectileTests::TestFlags)

bool FNLBladeQiProjectileLifetimeTest::RunTest(const FString& Parameters)
{
    FScopedCombatWorld Fixture;
    if (!TestTrue(TEXT("World initializes"), Fixture.IsReady())) return false;
    const FBody Source = Fixture.AddBody(ENLCombatFaction::Player, -100.0);
    if (!TestTrue(TEXT("Source initializes"), Source.IsReady())) return false;
    ANLCombatProjectile* Projectile = Fixture.Fire(Source, 0.05f);
    if (!TestNotNull(TEXT("Short-lived projectile initializes"), Projectile)) return false;

    Fixture.Step(0.02f);
    TestFalse(TEXT("The projectile remains alive before its deadline"), WasConsumed(Projectile));
    Fixture.Step(0.04f);
    TestTrue(TEXT("The projectile destroys itself after its game-time lifetime"), WasConsumed(Projectile));
    TestEqual(TEXT("Expiry cannot damage its owner"), Source.Vitals->GetHealth(), 100.0f);
    return true;
}

namespace NLBladeQiProjectileTests
{
    int32 CountLiveProjectiles(UWorld* World)
    {
        int32 Count = 0;
        for (TActorIterator<ANLCombatProjectile> It(World); It; ++It)
        {
            if (!It->IsActorBeingDestroyed()) ++Count;
        }
        return Count;
    }

    /** Native components register during deferred spawn, before asset/XR/checkpoint BeginPlay. */
    template <typename TPlayer>
    TPlayer* AddQueryOnlyPlayer(UWorld* World)
    {
        FActorSpawnParameters Parameters;
        Parameters.bDeferConstruction = true;
        Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        TPlayer* Player = World->SpawnActor<TPlayer>(
            FVector(-1000.0, 0.0, 100.0), FRotator::ZeroRotator, Parameters);
        if (Player)
        {
            Player->SetActorTickEnabled(false);
            Player->Vitals->MaxHealth = 100.0f;
            Player->Vitals->ResetVitals();
            Player->CombatIdentity->EnsureRuntimeId();
        }
        return Player;
    }
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiProjectileLaunchExitTest,
    "Nilin.Combat.BladeQi.Projectile.LaunchExitCooldownAndState", NLBladeQiProjectileTests::TestFlags)

bool FNLBladeQiProjectileLaunchExitTest::RunTest(const FString& Parameters)
{
    FScopedCombatWorld Fixture;
    if (!TestTrue(TEXT("World initializes"), Fixture.IsReady())) return false;
    ANLDesktopPlayerCharacter* Player = AddQueryOnlyPlayer<ANLDesktopPlayerCharacter>(Fixture.World);
    if (!TestNotNull(TEXT("Native desktop player initializes without BeginPlay"), Player)) return false;
    TestFalse(TEXT("The query fixture never enters player BeginPlay"), Player->HasActorBegunPlay());
    if (!TestTrue(TEXT("The camera component is registered"), Player->PlayerCamera->IsRegistered())) return false;
    Player->PlayerCamera->SetWorldLocationAndRotation(FVector(-20.0, 0.0, 100.0), FRotator::ZeroRotator);
    Player->BladeQiMuzzleOffsetCm = 40.0f;
    Player->BladeQiDefinition = Fixture.Definition;
    Fixture.Definition->CooldownSeconds = 1.0f;

    AActor* Wall = Fixture.AddWall(0.0);
    if (!TestNotNull(TEXT("A wall is registered between camera and muzzle"), Wall)) return false;
    CastChecked<UBoxComponent>(Wall->GetRootComponent())->SetBoxExtent(FVector(5.0, 100.0, 100.0), false);
    Player->FireBladeQi();
    TestEqual(TEXT("A muzzle offset cannot spawn through the thin wall"), CountLiveProjectiles(Fixture.World), 0);
    TestEqual(TEXT("A blocked launch spends no cooldown"), Player->GetBladeQiCooldownRemaining(), 0.0f);
    Wall->SetActorLocation(FVector(0.0, 1000.0, 100.0));

    // The fixture intentionally has no GameMode; WorldSettings' real pauser state
    // exercises the same UWorld::IsPaused gate without introducing gameplay startup.
    FActorSpawnParameters PauserParameters;
    PauserParameters.bDeferConstruction = true;
    APlayerState* Pauser = Fixture.World->SpawnActor<APlayerState>(PauserParameters);
    if (!TestNotNull(TEXT("A minimal pauser state initializes"), Pauser)) return false;
    Fixture.World->GetWorldSettings()->SetPauserPlayerState(Pauser);
    TestTrue(TEXT("The test world is actually paused"), Fixture.World->IsPaused());
    Player->FireBladeQi();
    TestEqual(TEXT("Pause rejects a ready launch"), CountLiveProjectiles(Fixture.World), 0);
    TestEqual(TEXT("Pause does not spend cooldown"), Player->GetBladeQiCooldownRemaining(), 0.0f);
    Fixture.World->GetWorldSettings()->SetPauserPlayerState(nullptr);
    TestFalse(TEXT("Removing the pauser resumes the world"), Fixture.World->IsPaused());

    Player->Vitals->Health = 0.0f;
    Player->FireBladeQi();
    TestEqual(TEXT("A dead player cannot launch"), CountLiveProjectiles(Fixture.World), 0);
    TestEqual(TEXT("Death does not spend cooldown"), Player->GetBladeQiCooldownRemaining(), 0.0f);
    Player->Vitals->ResetVitals();

    Player->FireBladeQi();
    TestEqual(TEXT("Clearing the exit permits a successful launch"), CountLiveProjectiles(Fixture.World), 1);
    TestTrue(TEXT("A successful launch starts cooldown"), Player->GetBladeQiCooldownRemaining() > 0.0f);
    Player->FireBladeQi();
    TestEqual(TEXT("An immediate second launch is rejected by cooldown"), CountLiveProjectiles(Fixture.World), 1);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FNLBladeQiProjectileTrackedHandExitTest,
    "Nilin.Combat.BladeQi.Projectile.TrackedHandOriginOcclusion", NLBladeQiProjectileTests::TestFlags)

bool FNLBladeQiProjectileTrackedHandExitTest::RunTest(const FString& Parameters)
{
    FScopedCombatWorld Fixture;
    if (!TestTrue(TEXT("World initializes"), Fixture.IsReady())) return false;
    ANLVRPlayerCharacter* Player = AddQueryOnlyPlayer<ANLVRPlayerCharacter>(Fixture.World);
    if (!TestNotNull(TEXT("Native VR components initialize without XR BeginPlay"), Player)) return false;
    TestFalse(TEXT("The VR fixture never starts XR or player BeginPlay"), Player->HasActorBegunPlay());
    if (!TestTrue(TEXT("Head and controller components are registered"),
        Player->PlayerCamera->IsRegistered() && Player->RightController->IsRegistered())) return false;
    Player->PlayerCamera->SetWorldLocationAndRotation(FVector(0.0, 0.0, 100.0), FRotator::ZeroRotator);
    Player->RightController->SetWorldLocationAndRotation(FVector(80.0, 0.0, 100.0), FRotator::ZeroRotator);
    TestTrue(TEXT("An unobstructed head-to-hand origin is accepted"), Player->HasClearSwordQiOrigin());

    AActor* Wall = Fixture.AddWall(40.0);
    if (!TestNotNull(TEXT("A wall separates the camera from the hand"), Wall)) return false;
    CastChecked<UBoxComponent>(Wall->GetRootComponent())->SetBoxExtent(FVector(5.0, 100.0, 100.0), false);
    TestFalse(TEXT("A hand and muzzle beyond the wall cannot fire through it"), Player->HasClearSwordQiOrigin());
    Wall->SetActorLocation(FVector(40.0, 1000.0, 100.0));
    TestTrue(TEXT("Removing the wall restores the valid origin"), Player->HasClearSwordQiOrigin());
    TestEqual(TEXT("Origin queries alone never spawn projectiles"), CountLiveProjectiles(Fixture.World), 0);
    return true;
}

#endif // WITH_DEV_AUTOMATION_TESTS
