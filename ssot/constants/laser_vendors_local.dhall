-- Repo-owned shop laser profiles, merged into laser_vendors.dhall. The template ships this empty on
-- purpose: lasers are shop specific (bed, kerf, materials). A new repo replaces `{=}` with records
-- built by ./laser_vendors/shop.dhall (see the example there) and selects one with
-- laser_sheet(vendor = "<slug>"). Nothing in the template may depend on a key defined here.
{=}
