"""Offline sanity checks for the School ERP addons.

Run without an Odoo server:
    python tools/validate_addons.py

Checks Python syntax, XML well-formedness, manifest data paths, module
dependencies, ACL/model coverage, sequences and XML reference integrity.
"""
import ast
import csv
import re
import sys
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
ADDONS_DIR = ROOT / 'addons'
NATIVE_MODULES = {
    'base', 'mail', 'portal', 'contacts', 'account', 'hr', 'website', 'web',
    'product', 'uom', 'analytic', 'calendar', 'resource', 'bus', 'digest',
}
ABSTRACT_MODELS = {'school.mixin'}

errors = []
warnings = []


def error(message):
    errors.append(message)


def warn(message):
    warnings.append(message)


def module_name(xml_id, current_module):
    return xml_id if '.' in xml_id else '%s.%s' % (current_module, xml_id)


def load_modules():
    modules = {}
    for directory in sorted(ADDONS_DIR.iterdir()):
        manifest_path = directory / '__manifest__.py'
        if not directory.is_dir() or not manifest_path.exists():
            continue
        try:
            manifest = ast.literal_eval(manifest_path.read_text(encoding='utf-8'))
        except (SyntaxError, ValueError) as exc:
            error('%s: manifest is not a valid literal: %s' % (directory.name, exc))
            continue
        modules[directory.name] = {'path': directory, 'manifest': manifest}
    return modules


def check_python(modules):
    for name, module in modules.items():
        for py_file in module['path'].rglob('*.py'):
            source = py_file.read_text(encoding='utf-8')
            try:
                compile(source, str(py_file), 'exec')
            except SyntaxError as exc:
                error('%s: Python syntax error in %s: %s' % (name, py_file.relative_to(ROOT), exc))
            if '_sql_constraints' in source:
                error('%s: deprecated _sql_constraints in %s; use models.Constraint'
                      % (name, py_file.relative_to(ROOT)))


def check_manifests(modules):
    for name, module in modules.items():
        manifest = module['manifest']
        for required in ('name', 'version', 'depends', 'data', 'installable'):
            if required not in manifest:
                error('%s: manifest missing "%s"' % (name, required))
        if not manifest.get('version', '').startswith('19.0.'):
            error('%s: version should start with 19.0.' % name)
        for dependency in manifest.get('depends', []):
            if dependency in modules:
                continue
            if dependency in NATIVE_MODULES:
                continue
            error('%s: unknown dependency "%s"' % (name, dependency))
        for data_file in manifest.get('data', []) + manifest.get('demo', []):
            if not (module['path'] / data_file).exists():
                error('%s: manifest data file missing: %s' % (name, data_file))


def collect_models_and_sequences(modules):
    models = {}
    sequences = set()
    for name, module in modules.items():
        for py_file in module['path'].rglob('*.py'):
            tree = ast.parse(py_file.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                for statement in node.body:
                    if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                        continue
                    target = statement.targets[0]
                    if not isinstance(target, ast.Name) or target.id != '_name':
                        continue
                    if isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
                        model = statement.value.value
                        if model in models:
                            error('%s: model "%s" also declared in %s' % (name, model, models[model]))
                        models[model] = name
    for name, module in modules.items():
        for py_file in module['path'].rglob('*.py'):
            source = py_file.read_text(encoding='utf-8')
            sequences.update(re.findall(r"next_by_code\(\s*['\"]([^'\"]+)['\"]", source))
    return models, sequences


def _class_attributes(node):
    attributes = {}
    for statement in node.body:
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
            target = statement.targets[0]
            if isinstance(target, ast.Name):
                attributes[target.id] = statement.value
    return attributes


def _literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [item.value for item in node.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)]
    return None


def collect_model_fields(modules):
    models = {}
    classes = []
    for name, module in modules.items():
        for py_file in module['path'].rglob('*.py'):
            tree = ast.parse(py_file.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    classes.append((name, py_file, node))

    def field_info(statement):
        value = statement.value
        if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)):
            return None
        if not (isinstance(value.func.value, ast.Name) and value.func.value.id == 'fields'):
            return None
        comodel = None
        if value.args and isinstance(value.args[0], ast.Constant) and isinstance(value.args[0].value, str):
            comodel = value.args[0].value
        return value.func.attr, comodel

    raw = {}
    for module_name_, py_file, node in classes:
        attributes = _class_attributes(node)
        model_name = _literal(attributes.get('_name'))
        inherit = _literal(attributes.get('_inherit'))
        inherited_models = [inherit] if isinstance(inherit, str) else (inherit or [])
        fields = {}
        for statement in node.body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target = statement.targets[0]
                if not isinstance(target, ast.Name):
                    continue
                info = field_info(statement)
                if info:
                    fields[target.id] = info[1]
        if model_name:
            raw.setdefault(model_name, {'fields': {}, 'inherits': []})
            raw[model_name]['fields'].update(fields)
            raw[model_name]['inherits'].extend(inherited_models)
        else:
            for parent in inherited_models:
                raw.setdefault(parent, {'fields': {}, 'inherits': []})
                raw[parent]['fields'].update(fields)

    def resolve(model, seen):
        if model in models:
            return models[model]
        if model in seen or model not in raw:
            return {}
        seen.add(model)
        result = dict(raw[model]['fields'])
        for parent in raw[model]['inherits']:
            result.update(resolve(parent, seen))
        models[model] = result
        return result

    for model in list(raw):
        resolve(model, set())
    return models


def check_view_fields(modules, model_fields):
    magic_fields = {
        'id', 'display_name', 'create_date', 'create_uid', 'write_date',
        'write_uid', '__last_update', 'message_follower_ids', 'message_ids',
        'activity_ids',
    }

    def validate_arch(element, model, location):
        fields = model_fields.get(model)
        for child in element:
            if child.tag != 'field':
                continue
            field_name = child.get('name')
            if not field_name:
                continue
            if fields is None:
                continue
            if field_name not in fields and field_name not in magic_fields:
                error('%s: field "%s" is not defined on model "%s"' % (location, field_name, model))
                continue
            comodel = fields.get(field_name)
            if comodel and comodel in model_fields and len(child):
                validate_arch(child, comodel, location)

    for module, module_data in modules.items():
        for data_file in module_data['manifest'].get('data', []):
            if not data_file.endswith('.xml'):
                continue
            xml_path = module_data['path'] / data_file
            if not xml_path.exists():
                continue
            tree = ElementTree.parse(xml_path)
            for record in tree.iter('record'):
                if record.get('model') != 'ir.ui.view':
                    continue
                view_fields = {field.get('name'): field for field in record.findall('field')}
                if 'inherit_id' in view_fields:
                    continue
                model = (view_fields.get('model').text or '').strip() if view_fields.get('model') is not None else ''
                arch = view_fields.get('arch')
                if not model or arch is None:
                    continue
                location = '%s: %s (%s)' % (module, data_file, record.get('id'))
                validate_arch(arch, model, location)


def collect_xml(modules):
    xml_ids = {}
    refs = []
    sequence_codes = set()
    used_xml_files = set()
    for name, module in modules.items():
        for data_file in module['manifest'].get('data', []) + module['manifest'].get('demo', []):
            if not data_file.endswith('.xml'):
                continue
            xml_path = module['path'] / data_file
            if not xml_path.exists():
                continue
            used_xml_files.add(xml_path.resolve())
            try:
                tree = ElementTree.parse(xml_path)
            except ElementTree.ParseError as exc:
                error('%s: XML error in %s: %s' % (name, data_file, exc))
                continue
            for element in tree.iter():
                element_id = element.get('id')
                if element.tag in ('record', 'menuitem', 'template', 'act_window', 'report') and element_id:
                    qualified = '%s.%s' % (name, element_id)
                    if qualified in xml_ids:
                        error('duplicate XML id %s in %s' % (qualified, data_file))
                    xml_ids[qualified] = xml_path
                if element.tag == 'menuitem':
                    for attribute in ('parent', 'action'):
                        value = element.get(attribute)
                        if value:
                            refs.append((name, data_file, module_name(value, name)))
                if element.tag == 'record':
                    for field in element.findall('field'):
                        if field.get('name') == 'code':
                            sequence_codes.add((field.text or '').strip())
                for attribute, value in element.attrib.items():
                    if attribute == 'ref':
                        refs.append((name, data_file, module_name(value, name)))
                    if attribute == 'eval' and 'ref(' in value:
                        for match in re.findall(r"ref\(\s*['\"]([^'\"]+)['\"]\s*\)", value):
                            refs.append((name, data_file, module_name(match, name)))
        for xml_file in module['path'].rglob('*.xml'):
            if xml_file.resolve() not in used_xml_files:
                warn('%s: XML file not listed in manifest: %s' % (name, xml_file.relative_to(module['path'])))
    return xml_ids, refs, sequence_codes


def check_refs(modules, models, xml_ids, refs):
    known_groups = {
        'school_core.group_school_user', 'school_core.group_school_manager',
        'school_core.group_school_teacher', 'school_core.group_school_accountant',
        'school_core.group_school_parent', 'school_core.group_school_student',
    }
    auto_model_ids = {
        '%s.%s' % (module, 'model_' + model.replace('.', '_'))
        for model, module in models.items()
    }
    for current_module, data_file, ref in refs:
        ref_module = ref.split('.')[0]
        if ref in xml_ids or ref in known_groups or ref in auto_model_ids:
            continue
        if ref_module in NATIVE_MODULES:
            continue
        if ref_module in modules:
            error('%s: %s references missing XML id "%s"' % (current_module, data_file, ref))
        else:
            warn('%s: %s references external module id "%s"' % (current_module, data_file, ref))


def check_acl_and_rules(modules, models, xml_ids):
    acl_models = set()
    known_group_prefix = 'school_core.group_school_'
    for name, module in modules.items():
        acl_path = module['path'] / 'security' / 'ir.model.access.csv'
        if not acl_path.exists():
            warn('%s: no security/ir.model.access.csv' % name)
            continue
        with acl_path.open(encoding='utf-8', newline='') as handle:
            rows = list(csv.DictReader(handle))
        seen = set()
        for row in rows:
            row_id = row.get('id', '')
            if row_id in seen:
                error('%s: duplicate ACL id "%s"' % (name, row_id))
            seen.add(row_id)
            model_ref = (row.get('model_id:id') or '').strip()
            if '.' in model_ref:
                model_ref = model_ref.split('.', 1)[1]
            if not model_ref.startswith('model_'):
                error('%s: ACL "%s" has invalid model_id "%s"' % (name, row_id, model_ref))
                continue
            acl_models.add(model_ref)
            model_name = next(
                (model for model in models if 'model_' + model.replace('.', '_') == model_ref),
                None,
            )
            if model_name is None:
                error('%s: ACL "%s" references unknown model id "%s"' % (name, row_id, model_ref))
            group_ref = module_name((row.get('group_id:id') or '').strip(), name)
            if not group_ref.startswith(known_group_prefix) and group_ref not in xml_ids:
                error('%s: ACL "%s" uses unknown group "%s"' % (name, row_id, group_ref))
            for column in ('perm_read', 'perm_write', 'perm_create', 'perm_unlink'):
                if row.get(column) not in ('0', '1'):
                    error('%s: ACL "%s" has invalid %s' % (name, row_id, column))
    for model in models:
        if model in ABSTRACT_MODELS:
            continue
        model_id = 'model_' + model.replace('.', '_')
        if model_id not in acl_models:
            error('model "%s" has no ACL entry' % model)


def check_sequences(modules, used_codes, declared_codes):
    for code in sorted(used_codes):
        if code not in declared_codes:
            error('sequence code "%s" is used but no ir.sequence declares it' % code)


def main():
    modules = load_modules()
    if not modules:
        print('No addons found in %s' % ADDONS_DIR)
        return 1
    check_python(modules)
    check_manifests(modules)
    models, used_sequences = collect_models_and_sequences(modules)
    model_fields = collect_model_fields(modules)
    xml_ids, refs, declared_sequences = collect_xml(modules)
    check_refs(modules, models, xml_ids, refs)
    check_acl_and_rules(modules, models, xml_ids)
    check_sequences(modules, used_sequences, declared_sequences)
    check_view_fields(modules, model_fields)

    print('Modules: %s' % ', '.join(sorted(modules)))
    print('Models: %d | XML ids: %d | Sequence codes used: %d' % (
        len(models), len(xml_ids), len(used_sequences)))
    for message in warnings:
        print('WARNING: %s' % message)
    for message in errors:
        print('ERROR: %s' % message)
    print('Result: %d error(s), %d warning(s)' % (len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
