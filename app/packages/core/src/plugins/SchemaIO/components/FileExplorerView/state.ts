import { useEffect, useState } from "react";
import { useOperatorExecutor } from "@fiftyone/operators";
import * as utils from "@fiftyone/utilities";

export function useCurrentFiles(defaultPath) {
  const [currentPath, _setCurrentPath] = useState(defaultPath);
  const executor = useOperatorExecutor("list_files");
  const currentFiles = executor.result?.files || [];
  const errorMessage = executor.error || executor.result?.error;

  const refresh = () => {
    executor.execute({ path: currentPath });
  };
  const setCurrentPath = (path) => {
    if (path) _setCurrentPath(path);
  };
  const onUpDir = () => {
    const parentPath = utils.resolveParent(currentPath);
    if (parentPath) _setCurrentPath(parentPath);
  };

  useEffect(refresh, [currentPath]);

  return {
    setCurrentPath,
    refresh,
    currentFiles,
    currentPath,
    errorMessage,
    onUpDir,
  };
}

export function useAvailableFileSystems() {
  const executor = useOperatorExecutor("list_files");
  const raw = executor.result?.filesystems || [];
  const filesystems = new Set(raw.map((name) => name.toLowerCase()));
  const hasAzure = filesystems.has("azure");
  const hasS3 = filesystems.has("s3");
  const hasGCP = filesystems.has("gcp");
  const hasMinIO = filesystems.has("minio");
  const hasLocal = filesystems.has("local");
  const hasCloud = hasAzure || hasS3 || hasGCP || hasMinIO;
  const refresh = () => {
    executor.execute({ list_filesystems: true });
  };

  useEffect(refresh, []);

  if (executor.error) {
    throw executor.error;
  }

  return { refresh, hasCloud, hasAzure, hasS3, hasGCP, hasMinIO, hasLocal };
}
