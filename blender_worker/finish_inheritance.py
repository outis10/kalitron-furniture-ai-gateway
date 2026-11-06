"""Snapshot-scoped module finish resolution, independent of Fusion and Blender."""

FAMILIES = frozenset(('FRONT', 'CARCASS', 'GOLA', 'PLINTH', 'COUNTERTOP'))
TARGET_FAMILIES = {'DOOR': 'FRONT', 'CARCASS': 'CARCASS', 'COUNTERTOP': 'COUNTERTOP'}


def validate_settings(settings, materials):
    if not isinstance(settings, dict) or set(settings) - {
            'source_export_id', 'role_families', 'project', 'instances', 'definitions', 'groups'}:
        raise ValueError('Unknown module_finishes fields')
    if not isinstance(settings.get('source_export_id'), str) or not settings['source_export_id']:
        raise ValueError('module_finishes requires source_export_id')
    policy = settings.get('role_families', {})
    if not isinstance(policy, dict) or any(
            not isinstance(role, str) or not role or not isinstance(family, str) or family not in FAMILIES
            for role, family in policy.items()):
        raise ValueError('Invalid explicit role-family policy')

    def slots(values):
        if not isinstance(values, dict) or any(
                family not in FAMILIES or not isinstance(material, str) or material not in materials
                for family, material in values.items()):
            raise ValueError('Invalid module family or material')

    slots(settings.get('project', {}))
    groups = settings.get('groups', {})
    if not isinstance(groups, dict) or set(groups) - {'LOWER', 'UPPER', 'BAR'}:
        raise ValueError('Invalid module groups')
    selected = set()
    for members in groups.values():
        if not isinstance(members, list):
            raise ValueError('Module group must be a list')
        for member in members:
            if not isinstance(member, str) or not member or member in selected:
                raise ValueError('Invalid or duplicate group member')
            selected.add(member)
    for kind in ('instances', 'definitions'):
        assignments = settings.get(kind, {})
        if not isinstance(assignments, dict):
            raise ValueError('Invalid module selectors: ' + kind)
        for selector, values in assignments.items():
            if not isinstance(selector, str) or not selector:
                raise ValueError('Empty module selector')
            slots(values)


class ModuleFinishResolver:
    def __init__(self, config, package, legacy_resolver):
        self.config = config
        self.settings = config['module_finishes']
        self.legacy_resolver = legacy_resolver
        validate_settings(self.settings, config['materials'])
        if self.settings['source_export_id'] != package.get('export_id'):
            raise ValueError('Module finishes belong to a different source export')
        self.instances = {}
        for instance in package['instances']:
            key = instance['instance_id']
            if key in self.instances:
                raise ValueError('Duplicate instance ID: ' + key)
            self.instances[key] = instance
        definitions = {i['definition_id'] for i in self.instances.values()}
        members = {m for group in self.settings.get('groups', {}).values() for m in group}
        if members - set(self.instances):
            raise ValueError('Unknown module group member')
        for key, valid in [('instances', self.instances), ('definitions', definitions)]:
            if set(self.settings.get(key, {})) - set(valid):
                raise ValueError('Unknown module ' + key + ' selector')
        for key, valid in [('instance_assignments', self.instances),
                           ('definition_assignments', definitions)]:
            if set(config.get(key, {})) - set(valid):
                raise ValueError('Unknown piece override selector: ' + key)

        self.chains = {}
        for key in self.instances:
            current, chain, seen = key, [], set()
            while current is not None:
                if current in seen:
                    raise ValueError('Module hierarchy cycle')
                if current not in self.instances:
                    raise ValueError('Missing module parent: ' + current)
                seen.add(current)
                chain.append(current)
                current = self.instances[current].get('parent_instance_id')
            self.chains[key] = tuple(chain)

    def resolve(self, instance):
        key = instance['instance_id']
        if key not in self.instances or instance != self.instances[key]:
            raise ValueError('Instance does not belong to this source export')
        target = instance.get('finish_target')
        if target is not None and not isinstance(target, str):
            raise ValueError('Invalid finish_target')
        family = (TARGET_FAMILIES.get(target) if target
                  else self.settings.get('role_families', {}).get(instance.get('role')))

        def result(material, source, selector=None):
            return {'material': material, 'source': source,
                    'family': family, 'scope_id': selector}

        for source, field in [('instance', 'instance_id'), ('definition', 'definition_id')]:
            selector = instance[field]
            material = self.config.get(source + '_assignments', {}).get(selector)
            if material is not None:
                return result(material, source, selector)
        if family:
            for ancestor in self.chains[key]:
                node = self.instances[ancestor]
                for source, selector in [('instances', ancestor), ('definitions', node['definition_id'])]:
                    material = self.settings.get(source, {}).get(selector, {}).get(family)
                    if material is not None:
                        return result(material, 'module_' + source[:-1], selector)
            material = self.settings.get('project', {}).get(family)
            if material is not None:
                return result(material, 'project_family', family)
        material, source = self.legacy_resolver(self.config, instance)
        return result(material, source)
