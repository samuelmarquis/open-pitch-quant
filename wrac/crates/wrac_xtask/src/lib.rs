use std::env;
use std::error::Error;
use std::path::PathBuf;

use clap::Parser;

mod cli;
mod commands;
mod context;
mod metadata;
mod plan;
mod profile;
mod targets;
mod util;
mod validation;

use cli::{Cli, Commands};
use commands::{clean, launch};
use context::{Context, available_packages};
use profile::BuildProfile;

pub type Result<T> = std::result::Result<T, Box<dyn Error>>;

#[derive(Debug, Clone)]
pub struct XtaskConfig {
    pub root: PathBuf,
    pub wrapper_dir: PathBuf,
    pub target_namespace: String,
}

pub fn run(config: XtaskConfig) -> Result<()> {
    load_workspace_dotenv(&config)?;
    let cli = Cli::parse();

    match cli.command {
        Commands::Build(args) => {
            // Keep build/install logic scoped to one plugin package at a time. A package may
            // export multiple plugin products; the shared Context is still the correct unit for
            // metadata, GUI assets, wrapper staging, and install paths.
            let mut failures = Vec::new();
            for package in selected_packages(&config, args.package.as_deref(), args.all)? {
                let ctx = Context::new(&config, &package)?;
                if let Err(err) = plan::run_build(&ctx, &args) {
                    if args.continue_on_error {
                        failures.push(format!("{package}: {err}"));
                    } else {
                        return Err(err);
                    }
                }
            }
            if !failures.is_empty() {
                return Err(failures.join("\n").into());
            }
        }
        Commands::Install(args) => {
            let mut failures = Vec::new();
            for package in selected_packages(&config, args.package.as_deref(), args.all)? {
                let ctx = Context::new(&config, &package)?;
                if let Err(err) = plan::run_install(&ctx, &args) {
                    if args.continue_on_error {
                        failures.push(format!("{package}: {err}"));
                    } else {
                        return Err(err);
                    }
                }
            }
            if !failures.is_empty() {
                return Err(failures.join("\n").into());
            }
        }
        Commands::Uninstall(args) => {
            let mut failures = Vec::new();
            for package in selected_packages(&config, args.package.as_deref(), args.all)? {
                let ctx = Context::new(&config, &package)?;
                if let Err(err) = plan::run_uninstall(&ctx, &args) {
                    if args.continue_on_error {
                        failures.push(format!("{package}: {err}"));
                    } else {
                        return Err(err);
                    }
                }
            }
            if !failures.is_empty() {
                return Err(failures.join("\n").into());
            }
        }
        Commands::Validate(args) => {
            let mut failures = Vec::new();
            for package in selected_packages(&config, args.package.as_deref(), args.all)? {
                let ctx = Context::new(&config, &package)?;
                if let Err(err) = plan::run_validate(&ctx, &args) {
                    if args.continue_on_error {
                        failures.push(format!("{package}: {err}"));
                    } else {
                        return Err(err);
                    }
                }
            }
            if !failures.is_empty() {
                return Err(failures.join("\n").into());
            }
        }
        Commands::Launch(args) => {
            let package = selected_package(&config, args.package.as_deref())?;
            let ctx = Context::new(&config, &package)?;
            // Validate product selection before the implicit standalone build.
            // A typo in --plugin-id is independent of artifacts and should not
            // spend time configuring CMake or building wrapper dependencies.
            commands::ensure_launch_target_exists(&ctx, args.plugin_id.as_deref())?;
            plan::run_build(&ctx, &args_for_launch_build(&args))?;
            launch(
                &ctx,
                BuildProfile::from_release(args.release),
                args.plugin_id.as_deref(),
            )?;
        }
        Commands::Clean(args) => {
            for package in selected_packages(&config, args.package.as_deref(), args.all)? {
                let ctx = Context::new(&config, &package)?;
                clean(&ctx)?;
            }
        }
    }

    Ok(())
}

fn load_workspace_dotenv(config: &XtaskConfig) -> Result<()> {
    let path = config.root.join(".env");
    if !path.exists() {
        return Ok(());
    }

    // `.env` is for project-local machine paths such as the AAX SDK. Do not
    // override the process environment so CI variables and one-off shell
    // overrides keep higher precedence than the repository-local file.
    for entry in dotenvy::from_path_iter(&path)? {
        let (key, value) = entry?;
        if env::var_os(&key).is_none() {
            // xtask loads .env before starting worker threads or subprocesses.
            // Mutating the process environment at this point lets the existing
            // command code and child processes consume one consistent source.
            unsafe {
                env::set_var(key, value);
            }
        }
    }
    Ok(())
}

fn selected_packages(
    config: &XtaskConfig,
    package: Option<&str>,
    all: bool,
) -> Result<Vec<String>> {
    if all {
        if package.is_some() {
            return Err("--package and --all cannot be used together".into());
        }
        let packages = available_packages(config)?
            .into_iter()
            .map(|package| package.package_name)
            .collect::<Vec<_>>();
        if packages.is_empty() {
            return Err("no WRAC plugin packages found in workspace members".into());
        }
        return Ok(packages);
    }
    if let Some(package) = package {
        return Ok(vec![package.to_string()]);
    }
    Ok(vec![selected_package(config, None)?])
}

fn selected_package(config: &XtaskConfig, package: Option<&str>) -> Result<String> {
    if let Some(package) = package {
        return Ok(package.to_string());
    }
    let packages = available_packages(config)?;
    match packages.as_slice() {
        [] => Err("no WRAC plugin packages found in workspace members".into()),
        [package] => Ok(package.package_name.clone()),
        _ => Err(format!(
            "multiple WRAC plugin packages found: {}. Use -p <PACKAGE> or --all.",
            packages
                .iter()
                .map(|package| package.package_name.as_str())
                .collect::<Vec<_>>()
                .join(", ")
        )
        .into()),
    }
}

fn args_for_launch_build(args: &cli::LaunchArgs) -> cli::BuildArgs {
    // launch is not "build the package defaults, then open an app"; it needs
    // exactly the standalone terminal task and its dependencies. Using the same
    // DAG entrypoint as `xtask build` keeps dependency behavior aligned without
    // accidentally pulling in supported plugin formats such as AAX.
    cli::BuildArgs {
        package: None,
        all: false,
        release: args.release,
        clean: false,
        dry_run: false,
        continue_on_error: false,
        target: vec![targets::Target::Standalone],
    }
}
