"use client";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { BookmarkIcon } from "lucide-react";

// Elements' Checkpoint (elements.ai-sdk.dev/components/checkpoint): marks a point in the
// conversation, with a button that restores the chat to it.

export const Checkpoint = ({ className, children, ...props }) => (
  <div className={cn("flex items-center gap-1 overflow-hidden text-muted-foreground", className)} {...props}>
    {children}
    <Separator className="flex-1" />
  </div>
);

export const CheckpointIcon = ({ className, children, ...props }) =>
  children ?? <BookmarkIcon className={cn("size-4 shrink-0", className)} aria-hidden="true" {...props} />;

export const CheckpointTrigger = ({ children, className, variant = "ghost", size = "sm", tooltip, ...props }) => {
  const button = (
    <Button className={cn("h-7 cursor-pointer border-0 bg-transparent px-2 text-xs text-muted-foreground hover:text-foreground", className)} size={size} type="button" variant={variant} {...props}>
      {children}
    </Button>
  );
  if (!tooltip) return button;
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent align="start" side="bottom">
          {tooltip}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
};
