CXX ?= g++
TBB_PREFIX ?= $(shell brew --prefix tbb 2>/dev/null)
TBB_INCLUDE_FLAGS = $(if $(TBB_PREFIX),-I$(TBB_PREFIX)/include,) -I../3rdParty/tbb/include
TBB_LINK_FLAGS = $(if $(TBB_PREFIX),-L$(TBB_PREFIX)/lib,)
OPT_FLAGS = -std=c++17 -O2 -DNDEBUG

output: DecisionMaking.o ForExport.o PreFlopEquity.o Range.o GameState.o GameContext.o Pot.o PlayerModel.o PostFlopParams.o PreFlopParams.o AllHandStrengths.o AllCounters.o HandStrengthCounter.o HandStrength.o Card.o Common.o
	$(CXX) -shared $(OPT_FLAGS) $(TBB_LINK_FLAGS) DecisionMaking.o ForExport.o PreFlopEquity.o Range.o GameState.o GameContext.o Pot.o PlayerModel.o PostFlopParams.o PreFlopParams.o AllHandStrengths.o AllCounters.o HandStrengthCounter.o HandStrength.o Card.o Common.o -o libdec_making.so -ltbb

COMPILE_FLAGS = $(OPT_FLAGS) $(TBB_INCLUDE_FLAGS) -c -fPIC

AllCounters.o: AllCounters.cpp AllCounters.h
	$(CXX) $(COMPILE_FLAGS) AllCounters.cpp

AllHandStrengths.o: AllHandStrengths.cpp AllHandStrengths.h
	$(CXX) $(COMPILE_FLAGS) AllHandStrengths.cpp

Card.o: Card.cpp Card.h
	$(CXX) $(COMPILE_FLAGS) Card.cpp

Common.o: Common.cpp Common.h
	$(CXX) $(COMPILE_FLAGS) Common.cpp

DecisionMaking.o: DecisionMaking.cpp
	$(CXX) $(COMPILE_FLAGS) DecisionMaking.cpp

ForExport.o: ForExport.cpp
	$(CXX) $(COMPILE_FLAGS) ForExport.cpp

GameContext.o: GameContext.cpp GameContext.h
	$(CXX) $(COMPILE_FLAGS) GameContext.cpp

GameState.o: GameState.cpp GameState.h
	$(CXX) $(COMPILE_FLAGS) GameState.cpp

HandStrength.o: HandStrength.cpp HandStrength.h
	$(CXX) $(COMPILE_FLAGS) HandStrength.cpp

HandStrengthCounter.o: HandStrengthCounter.cpp HandStrengthCounter.h
	$(CXX) $(COMPILE_FLAGS) HandStrengthCounter.cpp

PlayerModel.o: PlayerModel.cpp PlayerModel.h
	$(CXX) $(COMPILE_FLAGS) PlayerModel.cpp

PostFlopParams.o: PostFlopParams.cpp PostFlopParams.h
	$(CXX) $(COMPILE_FLAGS) PostFlopParams.cpp

Pot.o: Pot.cpp Pot.h
	$(CXX) $(COMPILE_FLAGS) Pot.cpp

PreFlopEquity.o: PreFlopEquity.cpp PreFlopEquity.h
	$(CXX) $(COMPILE_FLAGS) PreFlopEquity.cpp

PreFlopParams.o: PreFlopParams.cpp PreFlopParams.h
	$(CXX) $(COMPILE_FLAGS) PreFlopParams.cpp

Range.o: Range.cpp Range.h
	$(CXX) $(COMPILE_FLAGS) Range.cpp

clean:
	rm -f *.o
