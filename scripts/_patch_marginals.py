from pathlib import Path
p = Path(r"D:\factor\scripts\a_basis_marginals_20260926.py")
src = p.read_text(encoding="utf-8")
old = """            out.append(dict(
                candidate=name, scenario=scenario,
                s_new_corrected=s_new, s_new_old_bridge=s_old_bridge,
                d_raw_a=d_raw, d_na=d_raw / A_ANCHOR,
                points_A=PTS_A * d_raw, points_B=PTS_B * d_raw,
                d_nc_measured=d_nc_scenario,
                points_C=(BONUS_POINTS * W_C * d_nc_scenario) if d_nc_scenario is not None else None,
                points_total=A_PLUS_B := (PTS_A * d_raw + PTS_B * d_raw) + ((BONUS_POINTS * W_C * d_nc_scenario) if d_nc_scenario is not None else 0.0),
                d_raw_a_old_basis=d_raw_fixed_base,
                points_A_old_basis=PTS_A * d_raw_fixed_base,
            ))"""
new = """            points_c = (BONUS_POINTS * W_C * d_nc_scenario) if d_nc_scenario is not None else None
            out.append(dict(
                candidate=name, scenario=scenario,
                s_new_corrected=s_new, s_new_old_bridge=s_old_bridge,
                d_raw_a=d_raw, d_na=d_raw / A_ANCHOR,
                points_A=PTS_A * d_raw, points_B=PTS_B * d_raw,
                d_nc_measured=d_nc_scenario,
                points_C=points_c,
                points_A_plus_B=PTS_A * d_raw + PTS_B * d_raw,
                points_total=PTS_A * d_raw + PTS_B * d_raw + (points_c or 0.0),
                d_raw_a_old_basis=d_raw_fixed_base,
                points_A_old_basis=PTS_A * d_raw_fixed_base,
            ))"""
assert old in src
p.write_text(src.replace(old, new), encoding="utf-8")
print("patched")
