"""AutoData main entry point."""

import logging

from autodata.core.autodata import AutoData
from autodata.core.exceptions import AutoDataInitializationError
from autodata.utils.sys_utils import initialize

logger = logging.getLogger("AutoData")


def main() -> None:
    """Main entry point for AutoData."""
    try:
        # Initialize AutoData with configuration (includes merged CLI args)
        config = initialize()

        # Check if this is a dry run
        if config.dry_run:
            logger.info("Dry run completed successfully. Exiting.")
            return

        # Initialize AutoData with the loaded configuration
        autodata = AutoData(config=config)

        # Build the system
        autodata.build()

        # Generate and save graph visualization if requested
        if config.visualize_graph:
            autodata.visualize_graph()

        # Get task from merged config (CLI args override config file values)
        task = config.task
        if not task:
            logger.error("No task provided. Exiting.")
            return

        # Execute the task using configured strategy
        result = autodata.execute_task(task)
        if (
            config.checkpoint_config.checkpoint_enabled
            and config.checkpoint_config.auto_checkpoint
        ):
            autodata.save_checkpoint(pipeline_stage="post_execution")
        logger.info("Result: %s", result)

    except AutoDataInitializationError:
        logger.exception("AutoData initialization failed")
        raise
    except Exception:
        logger.exception("Task failed")
        raise


if __name__ == "__main__":
    # Run synchronously by default, or use --async flag for async execution
    main()
