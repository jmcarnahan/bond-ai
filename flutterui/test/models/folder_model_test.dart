import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/data/models/agent_model.dart';

void main() {
  group('AgentListItemModel sort_order parsing', () {
    test('fromJson parses sort_order when present', () {
      final json = {'id': 'a1', 'name': 'Test', 'sort_order': 3};
      final model = AgentListItemModel.fromJson(json);
      expect(model.sortOrder, 3);
    });

    test('fromJson sets sortOrder to null when absent', () {
      final json = {'id': 'a1', 'name': 'Test'};
      final model = AgentListItemModel.fromJson(json);
      expect(model.sortOrder, isNull);
    });

    test('toJson includes sort_order', () {
      const model = AgentListItemModel(id: 'a1', name: 'Test', sortOrder: 5);
      expect(model.toJson()['sort_order'], 5);
    });

    test('equality includes sortOrder', () {
      const a = AgentListItemModel(id: 'a1', name: 'T', sortOrder: 1);
      const b = AgentListItemModel(id: 'a1', name: 'T', sortOrder: 1);
      const c = AgentListItemModel(id: 'a1', name: 'T', sortOrder: 2);
      expect(a, b);
      expect(a, isNot(c));
    });
  });

  group('AgentListItemModel folder_id parsing', () {
    test('fromJson parses folder_id when present', () {
      final json = {
        'id': 'a1',
        'name': 'Test Agent',
        'folder_id': 'fld_work',
      };
      final model = AgentListItemModel.fromJson(json);
      expect(model.folderId, 'fld_work');
    });

    test('fromJson sets folderId to null when folder_id absent', () {
      final json = {
        'id': 'a2',
        'name': 'Unfiled Agent',
      };
      final model = AgentListItemModel.fromJson(json);
      expect(model.folderId, isNull);
    });

    test('fromJson sets folderId to null when folder_id is null', () {
      final json = {
        'id': 'a3',
        'name': 'Null Folder Agent',
        'folder_id': null,
      };
      final model = AgentListItemModel.fromJson(json);
      expect(model.folderId, isNull);
    });

    test('toJson includes folder_id', () {
      const model = AgentListItemModel(
        id: 'a1',
        name: 'Test',
        folderId: 'fld_123',
      );
      final json = model.toJson();
      expect(json['folder_id'], 'fld_123');
    });

    test('equality includes folderId', () {
      const a = AgentListItemModel(id: 'a1', name: 'Test', folderId: 'fld_1');
      const b = AgentListItemModel(id: 'a1', name: 'Test', folderId: 'fld_1');
      const c = AgentListItemModel(id: 'a1', name: 'Test', folderId: 'fld_2');
      const d = AgentListItemModel(id: 'a1', name: 'Test', folderId: null);
      expect(a, b);
      expect(a, isNot(c));
      expect(a, isNot(d));
    });
  });

  group('FolderModel', () {
    test('fromJson creates correct model', () {
      final json = {
        'id': 'fld_123',
        'name': 'Work Agents',
        'agent_count': 5,
        'sort_order': 1,
      };
      final model = FolderModel.fromJson(json);
      expect(model.id, 'fld_123');
      expect(model.name, 'Work Agents');
      expect(model.agentCount, 5);
      expect(model.sortOrder, 1);
    });

    test('fromJson handles missing optional fields', () {
      final json = {
        'id': 'fld_456',
        'name': 'Minimal',
      };
      final model = FolderModel.fromJson(json);
      expect(model.agentCount, 0);
      expect(model.sortOrder, 0);
    });

    test('toJson round-trips correctly', () {
      const model = FolderModel(
        id: 'fld_789',
        name: 'Personal',
        agentCount: 3,
        sortOrder: 2,
      );
      final json = model.toJson();
      final restored = FolderModel.fromJson(json);
      expect(restored, model);
    });

    test('equality works', () {
      const a = FolderModel(id: 'fld_1', name: 'A', agentCount: 1, sortOrder: 0);
      const b = FolderModel(id: 'fld_1', name: 'A', agentCount: 1, sortOrder: 0);
      const c = FolderModel(id: 'fld_2', name: 'A', agentCount: 1, sortOrder: 0);
      expect(a, b);
      expect(a, isNot(c));
    });

    test('hashCode is consistent with equality', () {
      const a = FolderModel(id: 'fld_1', name: 'A', agentCount: 1, sortOrder: 0);
      const b = FolderModel(id: 'fld_1', name: 'A', agentCount: 1, sortOrder: 0);
      expect(a.hashCode, b.hashCode);
    });
  });
}
