import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { Slot } from "radix-ui"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-lg font-ui border border-transparent bg-clip-padding text-sm whitespace-nowrap transition-all outline-none select-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 active:not-aria-[haspopup]:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20 dark:aria-invalid:border-destructive/50 dark:aria-invalid:ring-destructive/40 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        /* 主按钮（卷王 variant-5）：实心橙红填充 + 白字，hover 加深。
           用 accent-fill（暗色下不变亮），全站唯一的橙红填充面之一。 */
        default: "border-accent-fill bg-accent-fill text-white hover:bg-accent-ink hover:border-accent-ink",
        /* 次按钮：细线边 + 透明底，hover 转橙红边/字 + 墨色薄底 */
        outline:
          "border-hairline bg-transparent text-muted-ink hover:border-accent hover:bg-tint hover:text-accent aria-expanded:bg-tint aria-expanded:text-accent",
        secondary:
          "border-hairline bg-transparent text-muted-ink hover:border-accent hover:bg-tint hover:text-accent",
        ghost:
          "hover:bg-tint hover:text-accent aria-expanded:bg-tint aria-expanded:text-accent",
        destructive:
          "border-accent/40 bg-transparent text-accent hover:bg-wash focus-visible:border-accent/40 focus-visible:ring-accent/20",
        link: "text-accent underline-offset-4 hover:underline",
      },
      size: {
        default:
          "h-8 gap-1.5 px-2.5 has-data-[icon=inline-end]:pr-2 has-data-[icon=inline-start]:pl-2",
        xs: "h-6 gap-1 px-2 text-xs has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-7 gap-1 px-2.5 text-[0.8rem] has-data-[icon=inline-end]:pr-1.5 has-data-[icon=inline-start]:pl-1.5 [&_svg:not([class*='size-'])]:size-3.5",
        /* lg = 页面级主 CTA（生成试卷 / 提交判分 / 开始今日一练）：全站统一这一种尺寸 */
        lg: "h-11 gap-2 px-6 text-[15px] tracking-[0.03em] has-data-[icon=inline-end]:pr-5 has-data-[icon=inline-start]:pl-5",
        icon: "size-8",
        "icon-xs":
          "size-6 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm":
          "size-7",
        "icon-lg": "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
