import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Meta } from "./api";

const MetaCtx = createContext<Meta | null>(null);

export function MetaProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    api.meta().then(setMeta).catch(console.error);
  }, []);
  return <MetaCtx.Provider value={meta}>{children}</MetaCtx.Provider>;
}

export function useMeta(): Meta | null {
  return useContext(MetaCtx);
}
