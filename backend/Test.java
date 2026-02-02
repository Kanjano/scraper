public class Test {
    public void sum(int a, int b) {
        System.out.println("A");
    }
    public void sum(int a, float b) {
        System.out.println("B");
    }
    public void sum(float a, float b) {
        System.out.println("C");
    }
    public void sum(double... a) {
        System.out.println("D");
    }

    public static void main(String[] args) {
        Test t = new Test();
        t.sum(10, 16.25);
        t.sum(10, 24);
        t.sum(10.25, 10.25);
    }
}
