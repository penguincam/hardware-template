-- Laser and sheet vendor profiles keyed by slug (ssot/types/LaserVendor.dhall), rendered into
-- ssot/generated/constants.json as laser_vendors.<slug> for the laser_sheet macro, laser_export.py
-- and dxf_lint.py. example_service is a filled-in example of a cut service; a new repo replaces
-- its rows with its own vendor's published data. Shop lasers come from ./laser_vendors_local.dhall
-- (empty in the template). tools/ssot/type.sh checks every entry.
{ example_service = ./laser_vendors/example_service.dhall } /\ ./laser_vendors_local.dhall
