import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/agent_model.dart';

import 'package:flutterui/presentation/screens/agents/logic/agent_form_controller.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/providers/agent_provider.dart';

class MockCreateAgentFormNotifier extends CreateAgentFormNotifier {
  bool loadAgentForEditingCalled = false;
  bool resetStateCalled = false;
  bool saveAgentCalled = false;
  bool setLoadingCalled = false;
  String? lastLoadedAgentId;
  String? lastSavedAgentId;
  String lastName = '';
  String lastDescription = '';
  String lastInstructions = '';
  bool lastEnableCodeInterpreter = false;
  bool lastEnableFileSearch = false;
  bool lastLoadingState = false;
  bool saveAgentReturnValue = true;

  MockCreateAgentFormNotifier(super.ref);

  @override
  Future<void> loadAgentForEditing(String agentId) async {
    loadAgentForEditingCalled = true;
    lastLoadedAgentId = agentId;
  }

  @override
  void resetState() {
    resetStateCalled = true;
  }

  @override
  Future<bool> saveAgent({String? agentId}) async {
    saveAgentCalled = true;
    lastSavedAgentId = agentId;
    return saveAgentReturnValue;
  }

  @override
  void setName(String name) {
    lastName = name;
  }

  @override
  void setDescription(String description) {
    lastDescription = description;
  }

  @override
  void setInstructions(String instructions) {
    lastInstructions = instructions;
  }

  @override
  void setEnableCodeInterpreter(bool enable) {
    lastEnableCodeInterpreter = enable;
  }

  @override
  void setEnableFileSearch(bool enable) {
    lastEnableFileSearch = enable;
  }

  @override
  void setLoading(bool loading) {
    setLoadingCalled = true;
    lastLoadingState = loading;
  }
}

void main() {
  group('AgentFormController Tests', () {
    late MockCreateAgentFormNotifier mockFormNotifier;
    late ProviderContainer container;
    late GlobalKey<FormState> formKey;
    late TextEditingController nameController;
    late TextEditingController descriptionController;
    late TextEditingController instructionsController;

    setUp(() {
      formKey = GlobalKey<FormState>();
      nameController = TextEditingController();
      descriptionController = TextEditingController();
      instructionsController = TextEditingController();

      container = ProviderContainer(
        overrides: [
          createAgentFormProvider.overrideWith((ref) => MockCreateAgentFormNotifier(ref)),
          agentsProvider.overrideWith((ref) async => <AgentListItemModel>[]),
        ],
      );

      mockFormNotifier = container.read(createAgentFormProvider.notifier) as MockCreateAgentFormNotifier;
    });

    tearDown(() {
      nameController.dispose();
      descriptionController.dispose();
      instructionsController.dispose();
      container.dispose();
    });

    group('Constructor', () {
      testWidgets('should create controller with required parameters', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        expect(controller.formKey, equals(formKey));
        expect(controller.nameController, equals(nameController));
        expect(controller.descriptionController, equals(descriptionController));
        expect(controller.instructionsController, equals(instructionsController));
        expect(controller.agentId, isNull);
      });

      testWidgets('should create controller with agentId for editing', (tester) async {
        late AgentFormController editController;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  editController = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                    agentId: 'test-agent-id',
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        expect(editController.agentId, equals('test-agent-id'));
      });
    });

    group('initializeForm', () {
      testWidgets('should call loadAgentForEditing when agentId is provided', (tester) async {
        late AgentFormController editController;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  editController = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                    agentId: 'test-agent-id',
                  );
                  editController.initializeForm();
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        await tester.pump();

        expect(mockFormNotifier.loadAgentForEditingCalled, isTrue);
        expect(mockFormNotifier.lastLoadedAgentId, equals('test-agent-id'));
      });

      testWidgets('should call resetState when agentId is null', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  controller.initializeForm();
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        await tester.pump();

        expect(mockFormNotifier.resetStateCalled, isTrue);
      });
    });

    group('Form Field Changes', () {
      testWidgets('should call setName when onNameChanged is called', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        controller.onNameChanged('Test Agent');
        expect(mockFormNotifier.lastName, equals('Test Agent'));
      });

      testWidgets('should call setDescription when onDescriptionChanged is called', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        controller.onDescriptionChanged('Test Description');
        expect(mockFormNotifier.lastDescription, equals('Test Description'));
      });

      testWidgets('should call setInstructions when onInstructionsChanged is called', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        controller.onInstructionsChanged('Test Instructions');
        expect(mockFormNotifier.lastInstructions, equals('Test Instructions'));
      });

      testWidgets('should call setEnableCodeInterpreter when onCodeInterpreterChanged is called', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        controller.onCodeInterpreterChanged(true);
        expect(mockFormNotifier.lastEnableCodeInterpreter, isTrue);

        controller.onCodeInterpreterChanged(false);
        expect(mockFormNotifier.lastEnableCodeInterpreter, isFalse);
      });

      testWidgets('should call setEnableFileSearch when onFileSearchChanged is called', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        controller.onFileSearchChanged(true);
        expect(mockFormNotifier.lastEnableFileSearch, isTrue);

        controller.onFileSearchChanged(false);
        expect(mockFormNotifier.lastEnableFileSearch, isFalse);
      });
    });

    group('Form Validation', () {
      testWidgets('should return false when name is empty', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        nameController.text = '';
        instructionsController.text = 'Some instructions';

        expect(controller.isFormValid, isFalse);
      });

      testWidgets('should return false when instructions are empty', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        nameController.text = 'Test Agent';
        instructionsController.text = '';

        expect(controller.isFormValid, isFalse);
      });

      testWidgets('should return true when both name and instructions are provided', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        nameController.text = 'Test Agent';
        instructionsController.text = 'Test Instructions';

        expect(controller.isFormValid, isTrue);
      });
    });

    group('Editing State', () {
      testWidgets('should return false when agentId is null', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        expect(controller.isEditing, isFalse);
      });

      testWidgets('should return true when agentId is provided', (tester) async {
        late AgentFormController editController;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  editController = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                    agentId: 'test-agent-id',
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        expect(editController.isEditing, isTrue);
      });
    });

    group('saveAgent', () {
      testWidgets('should return false when form validation fails', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Form(
                key: formKey,
                child: Consumer(
                  builder: (context, ref, child) {
                    controller = AgentFormController(
                      ref: ref,
                      formKey: formKey,
                      nameController: nameController,
                      descriptionController: descriptionController,
                      instructionsController: instructionsController,
                    );
                    return Scaffold(
                      body: Column(
                        children: [
                          TextFormField(
                            controller: nameController,
                            validator: (value) => value?.isEmpty == true ? 'Required' : null,
                          ),
                          TextFormField(
                            controller: instructionsController,
                            validator: (value) => value?.isEmpty == true ? 'Required' : null,
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        );

        nameController.text = '';
        instructionsController.text = '';

        final result = await controller.saveAgent(tester.element(find.byType(Scaffold)));

        expect(result, isFalse);
        expect(mockFormNotifier.saveAgentCalled, isFalse);
      });

      testWidgets('should save agent successfully when form is valid', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Form(
                key: formKey,
                child: Consumer(
                  builder: (context, ref, child) {
                    controller = AgentFormController(
                      ref: ref,
                      formKey: formKey,
                      nameController: nameController,
                      descriptionController: descriptionController,
                      instructionsController: instructionsController,
                    );
                    return Scaffold(
                      body: Column(
                        children: [
                          TextFormField(
                            controller: nameController,
                            validator: (value) => value?.isEmpty == true ? 'Required' : null,
                          ),
                          TextFormField(
                            controller: instructionsController,
                            validator: (value) => value?.isEmpty == true ? 'Required' : null,
                          ),
                        ],
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        );

        nameController.text = 'Test Agent';
        descriptionController.text = 'Test Description';
        instructionsController.text = 'Test Instructions';

        final result = await controller.saveAgent(tester.element(find.byType(Scaffold)));

        expect(result, isTrue);
        expect(mockFormNotifier.saveAgentCalled, isTrue);
        expect(mockFormNotifier.lastName, equals('Test Agent'));
        expect(mockFormNotifier.lastDescription, equals('Test Description'));
        expect(mockFormNotifier.lastInstructions, equals('Test Instructions'));
      });
    });

    group('Edge Cases', () {
      testWidgets('should handle empty string values', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        controller.onNameChanged('');
        controller.onDescriptionChanged('');
        controller.onInstructionsChanged('');

        expect(mockFormNotifier.lastName, equals(''));
        expect(mockFormNotifier.lastDescription, equals(''));
        expect(mockFormNotifier.lastInstructions, equals(''));
      });

      testWidgets('should handle special characters in text fields', (tester) async {
        late AgentFormController controller;
        
        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  controller = AgentFormController(
                    ref: ref,
                    formKey: formKey,
                    nameController: nameController,
                    descriptionController: descriptionController,
                    instructionsController: instructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        const specialText = 'Agent with émojis 🤖 and spëcial chars @#\$%';
        
        controller.onNameChanged(specialText);
        controller.onDescriptionChanged(specialText);
        controller.onInstructionsChanged(specialText);

        expect(mockFormNotifier.lastName, equals(specialText));
        expect(mockFormNotifier.lastDescription, equals(specialText));
        expect(mockFormNotifier.lastInstructions, equals(specialText));
      });
    });

    group('dispose', () {
      testWidgets('should dispose all controllers', (tester) async {
        final testNameController = TextEditingController();
        final testDescriptionController = TextEditingController();
        final testInstructionsController = TextEditingController();
        late AgentFormController testController;

        await tester.pumpWidget(
          UncontrolledProviderScope(
            container: container,
            child: MaterialApp(
              home: Consumer(
                builder: (context, ref, child) {
                  testController = AgentFormController(
                    ref: ref,
                    formKey: GlobalKey<FormState>(),
                    nameController: testNameController,
                    descriptionController: testDescriptionController,
                    instructionsController: testInstructionsController,
                  );
                  return const Scaffold();
                },
              ),
            ),
          ),
        );

        testController.dispose();

        expect(() => testNameController.text, throwsFlutterError);
        expect(() => testDescriptionController.text, throwsFlutterError);
        expect(() => testInstructionsController.text, throwsFlutterError);
      });
    });
  });
}
