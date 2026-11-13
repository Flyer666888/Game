using UnrealBuildTool;

public class experiment : ModuleRules
{
	public experiment(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"AIModule",
			"NavigationSystem",
			"EnhancedInput",
			"HeadMountedDisplay",
			"XRBase"
		});
	}
}
