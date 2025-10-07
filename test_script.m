% test_script.m
% A simple MATLAB script to test execution

disp('Hello from MATLAB!');

% Calculate something simple
A = magic(3);   % 3x3 magic square
sumA = sum(A(:));

disp('The magic(3) matrix is:');
disp(A);

disp(['The sum of all elements is: ', num2str(sumA)]);

% Plot something
x = 0:0.1:2*pi;
y = sin(x);
figure;
plot(x, y, 'r-', 'LineWidth', 2);
title('Simple Sine Wave');
xlabel('x');
ylabel('sin(x)');
